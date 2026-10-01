import fs from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import vm from "node:vm";
import { parseHTML } from "linkedom";
import { Renderer } from "@takumi-rs/core";
import { fromHtml } from "@takumi-rs/helpers/html";
import { render as renderPdf } from "takumi-pdf";
import { exportedAfterShapeAttribute, exportedBeforeShapeAttribute, exportedShapeAttribute, extractBoxLayout, hideExportedBoxes } from "./box_layout.mjs";
import { writeContactSheets } from "./contact_sheets.mjs";
import { readFontMetrics } from "./font_metrics.mjs";
import { resampleImages } from "./image_resampling.mjs";
import { dataURIBytes, imageSize } from "./image_size.mjs";
import { generatedContentStyle, materializeGeneratedContent } from "./generated_content.mjs";
import { createInlineStyleFilter } from "./inline_styles.mjs";
import { createLayout, documentFragmentHtml } from "./layout_shim.mjs";
import { extractNativeCharts } from "./native_charts.mjs";
import { extractNativeTables, hideNativeTables, nativeCellAttribute, nativeTableAttribute } from "./native_tables.mjs";
import { measurePageGeometry } from "./page_geometry.mjs";
import { analyzePagePixels } from "./page_pixels.mjs";
import { exportedListAttribute, exportedTextAttribute, extractTextLayout, hideExportedText, insertMarkerProbes, markerProbeAttribute, markerProbeHostId } from "./text_layout.mjs";

const geometryThresholds = { pixelTolerance: 4, overlapRatioMinimum: 0.12, aspectRatioTolerance: 0.05, textPreviewLength: 40, smallestTextShareOfWidth: 0.01, titleLineMaximum: 3, backgroundShareOfSlide: 0.9 };
const pageAttribute = "data-render-page";
const pdfPageStyle = `[${pageAttribute}] { break-after: page; overflow: hidden; margin: 0 !important; } [${pageAttribute}="last"] { break-after: auto; }`;
const resetStyle = "html, body { margin: 0 !important; padding: 0 !important; }";
const textAttributes = { exportedTextAttribute, exportedListAttribute, markerProbeAttribute, markerProbeHostId, nativeCellAttribute };
const boxAttributes = { exportedShapeAttribute, exportedBeforeShapeAttribute, exportedAfterShapeAttribute, nativeTableAttribute };

function createTimer() {
  const started = performance.now();
  const marks = {};
  return {
    mark: (name) => {
      marks[name] = Math.round(performance.now() - started);
    },
    marks,
  };
}

function collectStyles(document, excludedSelector) {
  return Array.from(document.querySelectorAll("style"))
    .filter((style) => !excludedSelector || !style.matches(excludedSelector))
    .map((style) => style.textContent);
}

async function loadFonts(fontRequests) {
  return Promise.all(fontRequests.map(async (font) => ({ ...font, data: await fs.readFile(font.path), metrics: readFontMetrics(font.path) })));
}

function unquote(name) {
  return name.trim().replace(/^["']|["']$/g, "").toLowerCase();
}

function fontChooser(fonts) {
  return (familyList, weight) => {
    const families = String(familyList).split(",").map(unquote);
    const family = families.find((name) => fonts.some((font) => font.family.toLowerCase() === name)) || fonts[0]?.family.toLowerCase();
    const candidates = fonts.filter((font) => font.family.toLowerCase() === family);
    if (!candidates.length) return null;
    return candidates.reduce((best, font) => (Math.abs(font.weight - weight) < Math.abs(best.weight - weight) ? font : best)).metrics;
  };
}

function imageResolver(baseDirectory) {
  const cache = new Map();
  return (source) => {
    if (!source) return null;
    if (cache.has(source)) return cache.get(source);
    let bytes = null;
    if (source.startsWith("data:")) bytes = dataURIBytes(source);
    else if (!/^[a-z]+:/i.test(source) || source.startsWith("file:")) {
      const filePath = source.startsWith("file:") ? fileURLToPath(source) : path.resolve(baseDirectory, decodeURIComponent(source));
      try {
        bytes = readFileSync(filePath);
      } catch {
        bytes = null;
      }
    }
    cache.set(source, bytes);
    return bytes;
  };
}

function installGlobals(window, document, { htmlPath, fonts, styles, viewport, bytesOf }) {
  const families = [...new Set(fonts.map((font) => font.family))];
  Object.defineProperty(document, "fonts", { configurable: true, value: { forEach: (callback) => families.forEach((family) => callback({ family, status: "loaded" })), ready: Promise.resolve(), check: () => true } });
  Object.defineProperty(document, "baseURI", { configurable: true, value: pathToFileURL(htmlPath).href });
  window.getComputedStyle = styles.getComputedStyle;
  window.innerWidth = viewport.width;
  window.innerHeight = viewport.height;
  const imagePrototype = window.HTMLImageElement?.prototype;
  if (imagePrototype) {
    const sizeOf = (image) => {
      const bytes = bytesOf(image.getAttribute("src"));
      return bytes ? imageSize(bytes) : null;
    };
    Object.defineProperty(imagePrototype, "naturalWidth", { configurable: true, get() { return sizeOf(this)?.width || 0; } });
    Object.defineProperty(imagePrototype, "naturalHeight", { configurable: true, get() { return sizeOf(this)?.height || 0; } });
  }
  Object.assign(globalThis, {
    window,
    document,
    getComputedStyle: styles.getComputedStyle,
    Node: window.Node,
    NodeFilter: { SHOW_ALL: 0xffffffff, SHOW_ELEMENT: 1, SHOW_TEXT: 4 },
    SVGElement: window.SVGElement,
  });
}

function runScripts(window, document, selector) {
  if (!selector) return;
  const context = vm.createContext({ window, document, console, Intl, URL, setTimeout, clearTimeout, getComputedStyle: window.getComputedStyle, requestAnimationFrame: (callback) => setTimeout(callback, 0) });
  for (const script of document.querySelectorAll(selector)) {
    if (!script.getAttribute("src")) vm.runInContext(script.textContent, context);
  }
}

function topLevelPages(document, selector) {
  return Array.from(document.querySelectorAll(selector)).filter((page) => !page.parentElement?.closest(selector));
}

function imagesOf(elements, bytesOf) {
  const sources = new Set();
  for (const element of elements) {
    for (const image of [element, ...element.querySelectorAll("img, image")]) {
      const source = image.getAttribute?.("src") || image.getAttribute?.("href");
      if (source && !source.startsWith("data:")) sources.add(source);
    }
  }
  return Array.from(sources).flatMap((source) => {
    const data = bytesOf(source);
    return data ? [{ src: source, data }] : [];
  });
}

function rasterSize(size) {
  return { width: Math.ceil(size.width), height: Math.ceil(size.height) };
}

async function drawPage(renderer, layout, inlineStyles, page, css, images, withPixels) {
  const size = rasterSize(layout.sizeOf(page));
  await inlineStyles.prepare([page]);
  const parsed = fromHtml(inlineStyles.filterHtml(documentFragmentHtml([page])));
  const options = { width: size.width, height: size.height, css: [...css, resetStyle, ...parsed.css], images };
  const png = await renderer.render(parsed.node, { ...options, format: "png" });
  const pixels = withPixels ? analyzePagePixels(await renderer.render(parsed.node, { ...options, format: "raw" }), size.width, size.height) : null;
  return { png, pixels, size };
}

async function drawPages(renderer, layout, inlineStyles, pages, css, bytesOf, withPixels) {
  const drawn = [];
  for (const page of pages) drawn.push(await drawPage(renderer, layout, inlineStyles, page, css, imagesOf([page], bytesOf), withPixels));
  return drawn;
}

function pngPath(request, index) {
  return path.join(request.png.directory, `${request.png.prefix}.${String(index + 1).padStart(3, "0")}.png`);
}

async function writeDrawnPages(drawn, pathOf) {
  const written = drawn.map((page, index) => pathOf(index));
  if (written.length) await fs.mkdir(path.dirname(written[0]), { recursive: true });
  await Promise.all(drawn.map((page, index) => fs.writeFile(written[index], page.png)));
  return written;
}

async function writePdf(pdfPath, layout, inlineStyles, pages, css, fonts, bytesOf) {
  await inlineStyles.prepare(pages);
  pages.forEach((page, index) => page.setAttribute(pageAttribute, index === pages.length - 1 ? "last" : "page"));
  const size = layout.sizeOf(pages[0]);
  const html = inlineStyles.filterHtml(documentFragmentHtml(pages));
  pages.forEach((page) => page.removeAttribute(pageAttribute));
  const pdf = await renderPdf(html, {
    size: { width: size.width, height: size.height },
    margin: 0,
    fonts: fonts.map((font) => ({ name: font.family, weight: font.weight, style: font.style || "normal", data: font.data })),
    css: [...css, resetStyle, pdfPageStyle],
    images: imagesOf(pages, bytesOf),
  });
  await fs.mkdir(path.dirname(pdfPath), { recursive: true });
  await fs.writeFile(pdfPath, pdf);
}

async function writeLayers(request, renderer, layout, inlineStyles, document, pages, bytesOf) {
  for (const page of pages) await layout.layOut(page);
  const chartLayouts = extractNativeCharts({ pages });
  const tableLayouts = extractNativeTables({ pages });
  insertMarkerProbes({ ...textAttributes, pages });
  const probeHost = document.getElementById(markerProbeHostId);
  if (probeHost) await layout.layOut(probeHost);
  for (const page of pages) await layout.layOut(page);
  const textLayout = extractTextLayout({ ...textAttributes, pages });
  const boxLayouts = extractBoxLayout({ ...boxAttributes, pages });
  const slides = textLayout.slides.map((slide, index) => ({ ...slide, ...boxLayouts[index], ...chartLayouts[index], ...tableLayouts[index] }));
  hideExportedText(textAttributes);
  hideExportedBoxes(boxAttributes);
  hideNativeTables();
  const css = collectStyles(document, request.excludeStyles);
  const backgrounds = await drawPages(renderer, layout, inlineStyles, pages, [...css, ...(request.extraCss || []), generatedContentStyle], bytesOf, false);
  await writeDrawnPages(backgrounds, (index) => path.join(request.layers, `background.${String(index + 1).padStart(3, "0")}.png`));
  await fs.writeFile(path.join(request.layers, "layout.json"), `${JSON.stringify({ language: textLayout.language, slides }, null, 2)}\n`);
  return slides.length;
}

async function main() {
  const request = JSON.parse(await fs.readFile(process.argv[2], "utf8"));
  const timer = createTimer();
  const { window, document } = parseHTML(await fs.readFile(request.html, "utf8"));
  const resolveSource = imageResolver(path.dirname(request.html));
  let resampled = new Map();
  const bytesOf = (source) => resampled.get(source) || resolveSource(source);
  const fonts = await loadFonts(request.fonts);
  const renderer = new Renderer();
  for (const font of fonts) await renderer.registerFont({ name: font.family, weight: font.weight, style: font.style || "normal", data: font.data });
  const css = [...collectStyles(document, request.excludeStyles), ...(request.extraCss || []), generatedContentStyle];
  const viewport = request.viewport;
  const inlineStyles = createInlineStyleFilter(renderer);
  const layout = createLayout({ window, document, renderer, styleTexts: css, viewport, pageSelector: request.pageSelector, fontFor: fontChooser(fonts), inlineStyles });
  installGlobals(window, document, { htmlPath: request.html, fonts, styles: layout.styles, viewport, bytesOf });
  timer.mark("loaded");
  runScripts(window, document, request.scriptSelector);
  await new Promise((resolve) => setTimeout(resolve, 0));
  materializeGeneratedContent(document, topLevelPages(document, request.pageSelector), layout.styles);
  if (typeof window.renderHook === "function") await window.renderHook((element) => layout.layOut(element));
  const pages = topLevelPages(document, request.pageSelector);
  materializeGeneratedContent(document, pages, layout.styles);
  const unmapped = [];
  for (const page of pages) unmapped.push(...(await layout.layOut(page)).unmapped);
  timer.mark("laidOut");
  const result = { pages: pages.map((page, index) => ({ index: index + 1, ...layout.sizeOf(page) })), unmapped };
  if (request.geometry) {
    await fs.mkdir(path.dirname(request.geometry), { recursive: true });
    await fs.writeFile(request.geometry, `${JSON.stringify({ viewport, renderer: "takumi", slides: measurePageGeometry(pages, geometryThresholds) }, null, 2)}\n`);
    result.geometry = request.geometry;
    timer.mark("geometry");
  }
  resampled = await resampleImages(renderer, pages, bytesOf);
  timer.mark("resampled");
  if (request.png) {
    const drawn = await drawPages(renderer, layout, inlineStyles, pages, css, bytesOf, Boolean(request.pixels));
    result.png = await writeDrawnPages(drawn, (index) => pngPath(request, index));
    timer.mark("png");
    if (request.pixels) {
      await fs.writeFile(request.pixels, `${JSON.stringify({ pages: drawn.map((page) => page.pixels) }, null, 2)}\n`);
      result.pixels = request.pixels;
    }
    if (request.contactSheets) {
      const sheets = await writeContactSheets(renderer, request.contactSheets, drawn.map((page, index) => ({ number: index + 1, png: page.png })), drawn[0]?.size || viewport);
      await fs.writeFile(path.join(request.contactSheets, "contact-sheets.json"), `${JSON.stringify(sheets, null, 2)}\n`);
      result.contactSheets = sheets.map((sheet) => path.join(request.contactSheets, sheet.filename));
      timer.mark("contactSheets");
    }
  }
  if (request.pdf) {
    await writePdf(request.pdf, layout, inlineStyles, pages, css, fonts, bytesOf);
    result.pdf = request.pdf;
    timer.mark("pdf");
  }
  if (request.layers) {
    result.layers = { directory: request.layers, slides: await writeLayers(request, renderer, layout, inlineStyles, document, pages, bytesOf) };
    timer.mark("layers");
  }
  result.droppedStyles = inlineStyles.dropped();
  result.timings = timer.marks;
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
