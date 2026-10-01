import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs/promises";
import { accessSync, constants, createReadStream, statSync } from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { exportedListAttribute, exportedTextAttribute, extractTextLayout, hideExportedText, insertMarkerProbes, markerProbeAttribute, markerProbeHostId } from "./text_layout.mjs";
import { exportedAfterShapeAttribute, exportedBeforeShapeAttribute, exportedShapeAttribute, extractBoxLayout, hideExportedBoxes } from "./box_layout.mjs";

const slideWidth = 1600;
const slideHeight = 900;
const browserStartTimeoutMilliseconds = 15000;
const geometryFileName = "geometry.json";
const textLayersDirectoryName = "pptx-layers";
const exportedAttributes = { exportedTextAttribute, exportedListAttribute, markerProbeAttribute, markerProbeHostId };
const exportedBoxAttributes = { exportedShapeAttribute, exportedBeforeShapeAttribute, exportedAfterShapeAttribute };
const slideIsolationStyle = [
  "html, body { overflow: hidden !important; scrollbar-width: none; }",
  "section:not([data-internkim-render-target]) { display: none !important; }",
  "section[data-internkim-render-target] { position: fixed !important; left: 0 !important; top: 0 !important; margin: 0 !important; transform: none !important; visibility: visible !important; }",
].join("\n");
const geometryThresholds = { pixelTolerance: 4, overlapRatioMinimum: 0.12, aspectRatioTolerance: 0.05, textPreviewLength: 40 };

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
    argumentsFor: (port, profilePath) => ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profilePath}`, "--no-first-run", "--no-default-browser-check", "--password-store=basic", "--use-mock-keychain", "--disable-gpu", "--no-sandbox"],
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
  await renderDeckKit(page);
  renderProgress("navigated");

  const renderedSlideCount = await page.locator("section").count();
  if (renderedSlideCount !== deck.slideCount) {
    throw new Error(`expected ${deck.slideCount} slides, rendered ${renderedSlideCount}`);
  }

  await writeGeometry(page, deck);

  if (deck.enabledFormats.has("pdf")) {
    await page.pdf({
      path: path.join(deck.buildPath, `${deck.deckName}.pdf`),
      printBackground: true,
      width: `${slideWidth}px`,
      height: `${slideHeight}px`,
      margin: { top: "0", right: "0", bottom: "0", left: "0" },
    });
  }

  const layersPath = path.join(deck.reviewPath, textLayersDirectoryName);
  const textLayout = deck.enabledFormats.has("pptx") ? await measureTextLayout(page) : null;
  if (deck.enabledFormats.has("pptx") || deck.enabledFormats.has("review")) {
    await page.addStyleTag({ content: slideIsolationStyle });
    renderProgress(`screenshots ${deck.slideCount}`);
    await screenshotEachSlide(page, deck.slideCount, (number) => path.join(deck.reviewPath, `${deck.deckName}.${number}.png`));
  }
  if (textLayout) {
    await fs.mkdir(layersPath, { recursive: true });
    await page.evaluate(hideExportedText, exportedAttributes);
    await page.evaluate(hideExportedBoxes, exportedBoxAttributes);
    await screenshotEachSlide(page, deck.slideCount, (number) => path.join(layersPath, `background.${number}.png`));
    await fs.writeFile(path.join(layersPath, "layout.json"), `${JSON.stringify(textLayout, null, 2)}\n`);
    renderProgress(`text_layers ${textLayout.slides.length}`);
  }
  renderProgress("render_done");
}

async function measureTextLayout(page) {
  await page.evaluate(insertMarkerProbes, exportedAttributes);
  await layOutByPainting(page);
  const textLayout = await page.evaluate(extractTextLayout, exportedAttributes);
  const boxLayouts = await page.evaluate(extractBoxLayout, exportedBoxAttributes);
  return { ...textLayout, slides: textLayout.slides.map((slide, index) => ({ ...slide, ...boxLayouts[index] })) };
}

async function layOutByPainting(page) {
  await page.screenshot({ clip: { x: 0, y: 0, width: 1, height: 1 } });
}

async function screenshotEachSlide(page, slideCount, filePathOf) {
  for (let index = 0; index < slideCount; index += 1) {
    await page.evaluate((target) => {
      document.querySelectorAll("section").forEach((section, position) => section.toggleAttribute("data-internkim-render-target", position === target));
    }, index);
    await page.screenshot({
      path: filePathOf(String(index + 1).padStart(3, "0")),
      clip: { x: 0, y: 0, width: slideWidth, height: slideHeight },
      animations: "disabled",
    });
  }
}

async function writeGeometry(page, deck) {
  const slides = await page.evaluate(measureSlideGeometry, geometryThresholds);
  const geometry = { viewport: { width: slideWidth, height: slideHeight }, slides };
  await fs.writeFile(path.join(deck.reviewPath, geometryFileName), `${JSON.stringify(geometry, null, 2)}\n`);
  renderProgress(`geometry ${slides.length}`);
}

function measureSlideGeometry(thresholds) {
  const { pixelTolerance, overlapRatioMinimum, aspectRatioTolerance, textPreviewLength } = thresholds;

  const isMeasurable = (element) => {
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && !element.closest(".notes");
  };

  const describe = (element) => {
    const identifier = element.id ? `#${element.id}` : "";
    const classes = Array.from(element.classList).slice(0, 2).map((name) => `.${name}`).join("");
    const text = (element.textContent || "").replace(/\s+/g, " ").trim().slice(0, textPreviewLength);
    return { selector: `${element.tagName.toLowerCase()}${identifier}${classes}`, text };
  };

  const round = (value) => Math.round(value * 10) / 10;

  const roundRatio = (value) => Math.round(value * 1000) / 1000;

  const describeRect = (rect) => ({ left: round(rect.left), top: round(rect.top), right: round(rect.right), bottom: round(rect.bottom) });

  const elementsOf = (section) => [section, ...Array.from(section.querySelectorAll("*")).filter(isMeasurable)];

  const overflowingElements = (section) => {
    const overflowing = elementsOf(section).filter((element) => {
      if (element.clientWidth === 0 || element.clientHeight === 0) return false;
      return element.scrollHeight > element.clientHeight + pixelTolerance || element.scrollWidth > element.clientWidth + pixelTolerance;
    });
    return overflowing.filter((element) => !overflowing.some((other) => other !== element && element.contains(other)));
  };

  const describeOverflow = (element) => ({
    ...describe(element),
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  });

  const isOutsideFrame = (rect, frame) =>
    rect.width > 0 && rect.height > 0 &&
    (rect.left < frame.left - pixelTolerance || rect.top < frame.top - pixelTolerance ||
      rect.right > frame.right + pixelTolerance || rect.bottom > frame.bottom + pixelTolerance);

  const elementsOutsideFrame = (section) => {
    const frame = section.getBoundingClientRect();
    const isOutside = (element) => isOutsideFrame(element.getBoundingClientRect(), frame);
    return elementsOf(section)
      .slice(1)
      .filter((element) => isOutside(element) && !(element.parentElement !== section && isOutside(element.parentElement)));
  };

  const ownTextRects = (element) =>
    Array.from(element.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
      .flatMap((node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
      });

  const unionRect = (rects) => ({
    left: Math.min(...rects.map((rect) => rect.left)),
    top: Math.min(...rects.map((rect) => rect.top)),
    right: Math.max(...rects.map((rect) => rect.right)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  });

  const area = (rect) => Math.max(0, rect.right - rect.left) * Math.max(0, rect.bottom - rect.top);

  const overlapRatio = (first, second) => {
    const shared = area({
      left: Math.max(first.left, second.left),
      top: Math.max(first.top, second.top),
      right: Math.min(first.right, second.right),
      bottom: Math.min(first.bottom, second.bottom),
    });
    return shared / Math.min(area(first), area(second));
  };

  const overlappingText = (section) => {
    const boxes = elementsOf(section)
      .map((element) => ({ element, rects: ownTextRects(element) }))
      .filter((box) => box.rects.length > 0)
      .map((box) => ({ element: box.element, rect: unionRect(box.rects) }));
    const overlaps = [];
    boxes.forEach((first, index) => {
      boxes.slice(index + 1).forEach((second) => {
        if (first.element.contains(second.element) || second.element.contains(first.element)) return;
        const ratio = overlapRatio(first.rect, second.rect);
        if (ratio >= overlapRatioMinimum) {
          overlaps.push({ first: describe(first.element), second: describe(second.element), ratio: roundRatio(ratio) });
        }
      });
    });
    return overlaps;
  };

  const distortedImages = (section) =>
    Array.from(section.querySelectorAll("img"))
      .filter((image) => isMeasurable(image) && image.naturalWidth > 0 && image.naturalHeight > 0 && getComputedStyle(image).objectFit === "fill")
      .map((image) => {
        const rect = image.getBoundingClientRect();
        return { image, renderedRatio: rect.width / rect.height, naturalRatio: image.naturalWidth / image.naturalHeight };
      })
      .filter(({ renderedRatio, naturalRatio }) => Math.abs(renderedRatio / naturalRatio - 1) > aspectRatioTolerance)
      .map(({ image, renderedRatio, naturalRatio }) => ({ ...describe(image), renderedRatio: roundRatio(renderedRatio), naturalRatio: roundRatio(naturalRatio) }));

  const colorIsVisible = (color) => color !== "transparent" && !/(,\s*0\)|\/\s*0%?\))$/.test(color);

  const paintsBox = (style) =>
    colorIsVisible(style.backgroundColor) ||
    style.backgroundImage !== "none" ||
    style.boxShadow !== "none" ||
    ["Top", "Right", "Bottom", "Left"].some((side) => parseFloat(style[`border${side}Width`]) > 0 && style[`border${side}Style`] !== "none" && colorIsVisible(style[`border${side}Color`]));

  const mediaTags = new Set(["IMG", "SVG", "CANVAS", "VIDEO", "PICTURE", "OBJECT", "EMBED", "IFRAME"]);

  const intersection = (first, second) => ({
    left: Math.max(first.left, second.left),
    top: Math.max(first.top, second.top),
    right: Math.min(first.right, second.right),
    bottom: Math.min(first.bottom, second.bottom),
  });

  const visibleClipOf = (element, section) => {
    let clip = section.getBoundingClientRect();
    for (let ancestor = element.parentElement; ancestor && ancestor !== section; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      if (style.overflowX !== "visible" || style.overflowY !== "visible") clip = intersection(clip, ancestor.getBoundingClientRect());
    }
    return clip;
  };

  const contentRects = (section) => {
    const frame = section.getBoundingClientRect();
    const slideArea = frame.width * frame.height;
    return elementsOf(section).slice(1).flatMap((element) => {
      const rect = element.getBoundingClientRect();
      const isMedia = mediaTags.has(element.tagName.toUpperCase());
      const isBox = paintsBox(getComputedStyle(element)) && rect.width * rect.height < slideArea * 0.9;
      const clip = visibleClipOf(element, section);
      if (isMedia || isBox) return [intersection(rect, clip)];
      const style = getComputedStyle(element);
      const textClip = style.overflowX !== "visible" || style.overflowY !== "visible" ? intersection(clip, rect) : clip;
      return ownTextRects(element).map((content) => intersection(content, textClip));
    }).filter((rect) => rect.right > rect.left && rect.bottom > rect.top);
  };

  const contentBands = (section) => {
    const frame = section.getBoundingClientRect();
    const intervals = contentRects(section)
      .map((rect) => [rect.top - frame.top, rect.bottom - frame.top])
      .filter(([top, bottom]) => bottom > top)
      .sort((first, second) => first[0] - second[0]);
    const bands = [];
    for (const [top, bottom] of intervals) {
      const last = bands[bands.length - 1];
      if (last && top <= last[1]) last[1] = Math.max(last[1], bottom);
      else bands.push([top, bottom]);
    }
    return bands.map(([top, bottom]) => [round(top), round(bottom)]);
  };

  return Array.from(document.querySelectorAll("section")).map((section, index) => ({
    index: index + 1,
    height: round(section.getBoundingClientRect().height),
    contentBands: contentBands(section),
    overflow: overflowingElements(section).map(describeOverflow),
    outOfFrame: elementsOutsideFrame(section).map((element) => ({ ...describe(element), rect: describeRect(element.getBoundingClientRect()) })),
    overlaps: overlappingText(section),
    distortedImages: distortedImages(section),
  }));
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

async function renderDeckKit(page) {
  await page.evaluate(async () => {
    if (!window.deckKit) return;
    await window.deckKit.ready;
    window.deckKit.render();
  });
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
      entry === geometryFileName ||
      entry === textLayersDirectoryName ||
      entry === "slide-review.json" ||
      entry === "slide-review.md" ||
      entry === "render-source.txt"
    ) {
      await fs.rm(path.join(reviewPath, entry), { force: true, recursive: true });
    }
  }
}


main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
