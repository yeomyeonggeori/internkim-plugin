import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs/promises";
import { accessSync, constants, createReadStream, statSync } from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const slideWidth = 1600;
const slideHeight = 900;
const browserStartTimeoutMilliseconds = 15000;

function renderProgress(label) {
  process.stderr.write(`[render] ${label} ${Math.floor(Date.now() / 1000)}\n`);
}

async function main() {
  const [sourcePath, deckName, buildPath, formats] = process.argv.slice(2);
  if (!sourcePath || !deckName || !buildPath || !formats) {
    console.error("Usage: html_render.mjs <source.html> <deck-name> <build-dir> <formats>");
    process.exit(2);
  }

  const enabledFormats = new Set(formats.split(",").map((value) => value.trim()).filter(Boolean));
  const reviewPath = path.join(buildPath, "review");
  await fs.mkdir(reviewPath, { recursive: true });
  await removePreviousReviewFiles(reviewPath, deckName);

  const slideCount = await countSlides(sourcePath);
  if (slideCount === 0) {
    throw new Error("slides.html must contain at least one <section> slide");
  }

  const deck = { sourcePath, deckName, buildPath, reviewPath, enabledFormats, slideCount };
  const browser = installedDevToolsBrowser();
  if (!browser) {
    throw new Error("no browser that speaks the Chrome DevTools Protocol was found");
  }
  try {
    await renderWithDevToolsBrowser(browser, deck);
  } catch (error) {
    renderProgress(`render_failed ${compactErrorMessage(error)}`);
    await removePreviousReviewFiles(reviewPath, deckName);
    throw error;
  }
}

const devToolsBrowsers = [
  { program: "moli", argumentsFor: (port) => ["serve", "--layout", "--resource", "--port", String(port)] },
  ...["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"].map((program) => ({
    program,
    argumentsFor: (port, profilePath) => ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profilePath}`, "--no-first-run", "--no-default-browser-check", "--disable-gpu", "--no-sandbox"],
  })),
];

function installedDevToolsBrowser() {
  for (const browser of devToolsBrowsers) {
    const executablePath = executablePathOf(browser.program);
    if (executablePath) {
      return { ...browser, executablePath };
    }
  }
  return null;
}

function executablePathOf(program) {
  const candidatePaths = path.isAbsolute(program)
    ? [program]
    : (process.env.PATH || "").split(path.delimiter).filter(Boolean).map((directoryPath) => path.join(directoryPath, program));
  for (const candidatePath of candidatePaths) {
    try {
      accessSync(candidatePath, constants.X_OK);
      return candidatePath;
    } catch {
      continue;
    }
  }
  return null;
}

async function renderWithDevToolsBrowser(browser, deck) {
  const { chromium: devToolsClient } = await import("playwright-core");
  const deckServer = await serveDirectory(path.dirname(deck.sourcePath));
  const profilePath = await fs.mkdtemp(path.join(os.tmpdir(), "presentation-browser-"));
  const port = await unusedPort();
  renderProgress(`browser_start ${path.basename(browser.program)}`);
  const browserProcess = spawn(browser.executablePath, browser.argumentsFor(port, profilePath), { stdio: ["ignore", "ignore", "inherit"] });
  try {
    await waitForDevTools(port);
    const connection = await devToolsClient.connectOverCDP(`http://127.0.0.1:${port}`, { timeout: browserStartTimeoutMilliseconds });
    renderProgress("launched");
    try {
      await renderDeck(connection, deck, deckServer.urlOf(path.basename(deck.sourcePath)), deckServer.origin);
    } finally {
      await connection.close().catch(() => {});
    }
  } finally {
    await stopBrowser(browserProcess);
    deckServer.close();
    await fs.rm(profilePath, { recursive: true, force: true });
  }
}


async function renderDeck(browser, deck, sourceURL, allowedURLPrefix) {
  const page = await browser.newPage({ viewport: { width: slideWidth, height: slideHeight }, deviceScaleFactor: 1 });
  await page.route("**/*", (route) => {
    const requestURL = route.request().url();
    if (requestURL.startsWith(allowedURLPrefix) || requestURL.startsWith("data:")) {
      route.continue();
    } else {
      route.abort();
    }
  });
  renderProgress("navigating");
  await page.goto(sourceURL, { waitUntil: "load", timeout: 30000 }).catch(() => {});
  await page.emulateMedia({ media: "print" });
  await waitForFonts(page);
  renderProgress("navigated");

  const renderedSlideCount = await page.locator("section").count();
  if (renderedSlideCount !== deck.slideCount) {
    throw new Error(`expected ${deck.slideCount} slides, rendered ${renderedSlideCount}`);
  }

  if (deck.enabledFormats.has("pdf")) {
    await page.pdf({
      path: path.join(deck.buildPath, `${deck.deckName}.pdf`),
      printBackground: true,
      width: `${slideWidth}px`,
      height: `${slideHeight}px`,
      margin: { top: "0", right: "0", bottom: "0", left: "0" },
    });
  }

  if (deck.enabledFormats.has("pptx") || deck.enabledFormats.has("review")) {
    const slides = await page.locator("section").all();
    renderProgress(`screenshots ${slides.length}`);
    for (let index = 0; index < slides.length; index += 1) {
      await slides[index].screenshot({
        path: path.join(deck.reviewPath, `${deck.deckName}.${String(index + 1).padStart(3, "0")}.png`),
        animations: "disabled",
      });
    }
  }
  renderProgress("render_done");
}

async function stopBrowser(browserProcess) {
  if (browserProcess.exitCode !== null) {
    return;
  }
  const exited = new Promise((resolve) => browserProcess.once("exit", () => resolve(true)));
  browserProcess.kill("SIGTERM");
  const hasExited = await Promise.race([exited, new Promise((resolve) => setTimeout(() => resolve(false), 2000))]);
  if (!hasExited) {
    renderProgress("browser_killed");
    browserProcess.kill("SIGKILL");
  }
}

const contentTypes = {
  ".css": "text/css",
  ".gif": "image/gif",
  ".html": "text/html; charset=utf-8",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript",
  ".json": "application/json",
  ".otf": "font/otf",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ttf": "font/ttf",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

async function serveDirectory(rootPath) {
  const secretPrefix = `/${randomBytes(16).toString("hex")}/`;
  const server = http.createServer((request, response) => {
    const filePath = servedFilePath(rootPath, secretPrefix, request.url);
    if (!filePath) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, { "content-type": contentTypes[path.extname(filePath).toLowerCase()] || "application/octet-stream" });
    createReadStream(filePath).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}${secretPrefix}`;
  return {
    origin,
    urlOf: (relativePath) => origin + encodeURI(relativePath),
    close: () => server.close(),
  };
}

function servedFilePath(rootPath, secretPrefix, requestURL) {
  const requestPath = decodeURIComponent(new URL(requestURL, "http://127.0.0.1").pathname);
  if (!requestPath.startsWith(secretPrefix)) {
    return null;
  }
  const filePath = path.resolve(rootPath, requestPath.slice(secretPrefix.length));
  const relativePath = path.relative(rootPath, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    return null;
  }
  return statSync(filePath, { throwIfNoEntry: false })?.isFile() ? filePath : null;
}

function unusedPort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

async function waitForDevTools(port) {
  const deadline = Date.now() + browserStartTimeoutMilliseconds;
  while (Date.now() < deadline) {
    const answer = await fetch(`http://127.0.0.1:${port}/json/version`).catch(() => null);
    if (answer?.ok) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`the browser did not answer the DevTools Protocol on port ${port}`);
}






async function countSlides(sourcePath) {
  const sourceText = await fs.readFile(sourcePath, "utf8");
  return Array.from(sourceText.matchAll(/<section\b/gi)).length;
}




function compactErrorMessage(error) {
  return String(error?.message || error).replace(/\s+/g, " ").slice(0, 180);
}

async function waitForFonts(page) {
  await Promise.race([
    page.evaluate(async () => {
      if (document.fonts) {
        await document.fonts.ready;
      }
    }),
    new Promise((resolve) => setTimeout(resolve, 5000)),
  ]);
}

async function removePreviousReviewFiles(reviewPath, deckName) {
  const entries = await fs.readdir(reviewPath).catch(() => []);
  for (const entry of entries) {
    if (
      entry.startsWith(`${deckName}.`) ||
      entry.startsWith("contact-sheet-") ||
      entry.startsWith("fit-review") ||
      entry === "slide-review.json" ||
      entry === "slide-review.md" ||
      entry === "render-source.txt"
    ) {
      await fs.rm(path.join(reviewPath, entry), { force: true });
    }
  }
}


main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
