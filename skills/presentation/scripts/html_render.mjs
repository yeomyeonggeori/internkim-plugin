import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs/promises";
import { accessSync, constants, createReadStream, existsSync, statSync } from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const slideWidth = 1600;
const slideHeight = 900;
const chromiumCommandTimeoutMilliseconds = 45000;
const playwrightLaunchTimeoutMilliseconds = Number(process.env.INTERNKIM_PLAYWRIGHT_LAUNCH_TIMEOUT_MS || "15000");

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
  const moliPath = executableOnPath("moli");
  try {
    if (moliPath) {
      await renderWithMoli(moliPath, deck);
    } else {
      await renderWithPlaywright(deck);
    }
  } catch (error) {
    renderProgress(`playwright_failed ${compactErrorMessage(error)}`);
    await removePreviousReviewFiles(reviewPath, deckName);
    await renderWithChromiumCommand(sourcePath, deckName, buildPath, enabledFormats, slideCount);
  }
}

async function renderWithMoli(moliPath, deck) {
  const { chromium } = await import("playwright-core");
  const deckServer = await serveDirectory(path.dirname(deck.sourcePath));
  const cdpPort = await unusedPort();
  renderProgress("moli_start");
  const moliProcess = spawn(moliPath, ["serve", "--layout", "--resource", "--port", String(cdpPort)], { stdio: ["ignore", "ignore", "inherit"] });
  try {
    await waitForCDP(cdpPort);
    const browser = await chromium.connectOverCDP(`http://127.0.0.1:${cdpPort}`, { timeout: playwrightLaunchTimeoutMilliseconds });
    renderProgress("launched");
    try {
      await renderDeck(browser, deck, deckServer.urlOf(path.basename(deck.sourcePath)), deckServer.origin);
    } finally {
      await browser.close().catch(() => {});
    }
  } finally {
    moliProcess.kill("SIGTERM");
    deckServer.close();
  }
}

async function renderWithPlaywright(deck) {
  const { chromium } = await import("playwright-core");
  renderProgress("launch_start");
  const browser = await chromium.launch({
    executablePath: chromiumExecutablePath(),
    headless: true,
    timeout: playwrightLaunchTimeoutMilliseconds,
    args: [
      "--disable-background-networking",
      "--disable-background-timer-throttling",
      "--disable-breakpad",
      "--disable-client-side-phishing-detection",
      "--disable-component-update",
      "--disable-default-apps",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      "--disable-hang-monitor",
      "--disable-ipc-flooding-protection",
      "--disable-popup-blocking",
      "--disable-prompt-on-repost",
      "--disable-renderer-backgrounding",
      "--disable-sync",
      "--metrics-recording-only",
      "--no-default-browser-check",
      "--no-first-run",
      "--no-sandbox",
      "--password-store=basic",
      "--use-mock-keychain",
    ],
  });
  renderProgress("launched");
  try {
    await renderDeck(browser, deck, fileURL(deck.sourcePath), "file:");
  } finally {
    await browser.close();
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

async function waitForCDP(port) {
  const deadline = Date.now() + playwrightLaunchTimeoutMilliseconds;
  while (Date.now() < deadline) {
    const answer = await fetch(`http://127.0.0.1:${port}/json/version`).catch(() => null);
    if (answer?.ok) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`moli did not answer CDP on port ${port}`);
}

function executableOnPath(programName) {
  for (const directoryPath of (process.env.PATH || "").split(path.delimiter).filter(Boolean)) {
    const candidatePath = path.join(directoryPath, programName);
    try {
      accessSync(candidatePath, constants.X_OK);
      return candidatePath;
    } catch {
      continue;
    }
  }
  return null;
}

async function renderWithChromiumCommand(sourcePath, deckName, buildPath, enabledFormats, slideCount) {
  renderProgress("chromium_command_start");
  const browserPath = chromiumExecutablePath();
  const profilePath = await fs.mkdtemp(path.join(os.tmpdir(), "internkim-chromium-"));
  try {
    if (enabledFormats.has("pdf")) {
      await runChromium(browserPath, [
        ...chromiumCommandArguments(profilePath),
        `--print-to-pdf=${path.join(buildPath, `${deckName}.pdf`)}`,
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        fileURL(sourcePath),
      ]);
    }
    if (enabledFormats.has("pptx") || enabledFormats.has("review")) {
      renderProgress(`screenshots ${slideCount}`);
      for (let index = 1; index <= slideCount; index += 1) {
        const imagePath = path.join(buildPath, "review", `${deckName}.${String(index).padStart(3, "0")}.png`);
        await runChromium(browserPath, [
          ...chromiumCommandArguments(profilePath),
          `--window-size=${slideWidth},${slideHeight}`,
          `--screenshot=${imagePath}`,
          exportSlideURL(sourcePath, index),
        ]);
        await assertFileCreated(imagePath, `slide ${index} screenshot`);
      }
    }
    renderProgress("render_done");
  } finally {
    await fs.rm(profilePath, { recursive: true, force: true });
  }
}

function chromiumCommandArguments(profilePath) {
  return [
    "--headless",
    "--no-sandbox",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-breakpad",
    "--disable-client-side-phishing-detection",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-sync",
    "--hide-scrollbars",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-default-browser-check",
    "--no-first-run",
    "--password-store=basic",
    "--run-all-compositor-stages-before-draw",
    "--use-mock-keychain",
    "--virtual-time-budget=8000",
    `--user-data-dir=${profilePath}`,
  ];
}

async function runChromium(browserPath, argumentsList) {
  const completedProcess = await runCommand(browserPath, argumentsList, chromiumCommandTimeoutMilliseconds);
  if (completedProcess.exitCode !== 0) {
    throw new Error(`chromium exited ${completedProcess.exitCode}: ${completedProcess.stderr.slice(-1200)}`);
  }
}

function runCommand(command, argumentsList, timeoutMilliseconds) {
  return new Promise((resolve, reject) => {
    const childProcess = spawn(command, argumentsList, {
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        DBUS_SESSION_BUS_ADDRESS: process.env.DBUS_SESSION_BUS_ADDRESS || "/dev/null",
      },
    });
    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      childProcess.kill("SIGKILL");
      reject(new Error(`${path.basename(command)} timed out after ${timeoutMilliseconds}ms`));
    }, timeoutMilliseconds);
    childProcess.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    childProcess.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    childProcess.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    childProcess.on("close", (exitCode) => {
      clearTimeout(timeout);
      resolve({ exitCode, stdout, stderr });
    });
  });
}

async function countSlides(sourcePath) {
  const sourceText = await fs.readFile(sourcePath, "utf8");
  return Array.from(sourceText.matchAll(/<section\b/gi)).length;
}

function fileURL(sourcePath) {
  return pathToFileURL(sourcePath).toString();
}

function exportSlideURL(sourcePath, slideIndex) {
  const url = new URL(fileURL(sourcePath));
  url.searchParams.set("internkim-export", "1");
  url.hash = `slide-${slideIndex}`;
  return url.toString();
}

async function assertFileCreated(filePath, label) {
  const fileInfo = await fs.stat(filePath).catch(() => null);
  if (!fileInfo || fileInfo.size === 0) {
    throw new Error(`${label} was not created`);
  }
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

function chromiumExecutablePath() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.PUPPETEER_EXECUTABLE_PATH,
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }
  throw new Error("Chromium executable not found");
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
