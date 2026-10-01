import { fromHtml } from "@takumi-rs/helpers/html";
import { imageSize } from "./image_size.mjs";

const pixelDensity = 2;
const worthwhileShrink = 0.85;
const jpegQuality = 86;
const keyPrefix = "internkim-image-";

function pngHasAlpha(bytes) {
  return [4, 6].includes(bytes[25]) || bytes.includes("tRNS");
}

function webpHasAlpha(bytes) {
  const chunk = bytes.toString("ascii", 12, 16);
  if (chunk === "VP8X") return (bytes[20] & 0x10) !== 0;
  if (chunk === "VP8L") return ((bytes.readUInt32LE(21) >> 28) & 1) === 1;
  return false;
}

function isJpeg(bytes) {
  return bytes.length > 2 && bytes[0] === 0xff && bytes[1] === 0xd8;
}

function hasAlpha(bytes) {
  if (bytes.toString("ascii", 1, 4) === "PNG") return pngHasAlpha(bytes);
  if (bytes.toString("ascii", 8, 12) === "WEBP") return webpHasAlpha(bytes);
  return bytes.toString("ascii", 0, 3) === "GIF";
}

function drawnBoxes(pages) {
  const boxes = new Map();
  for (const page of pages) {
    for (const image of page.querySelectorAll("img")) {
      const source = image.getAttribute("src");
      const rect = image.getBoundingClientRect();
      if (!source || rect.width <= 0 || rect.height <= 0) continue;
      const previous = boxes.get(source) || { width: 0, height: 0, images: [] };
      boxes.set(source, { width: Math.max(previous.width, rect.width), height: Math.max(previous.height, rect.height), images: [...previous.images, image] });
    }
  }
  return boxes;
}

function targetSize(natural, box) {
  const scale = Math.min(1, Math.max((pixelDensity * box.width) / natural.width, (pixelDensity * box.height) / natural.height));
  return { scale, width: Math.max(1, Math.round(natural.width * scale)), height: Math.max(1, Math.round(natural.height * scale)) };
}

async function resample(renderer, bytes, target, format) {
  const parsed = fromHtml(`<img src="source" style="display:block;width:${target.width}px;height:${target.height}px">`);
  return renderer.render(parsed.node, { width: target.width, height: target.height, css: parsed.css, format, quality: jpegQuality, images: [{ src: "source", data: bytes }] });
}

export async function resampleImages(renderer, pages, bytesOf) {
  const resampled = new Map();
  let index = 0;
  for (const [source, box] of drawnBoxes(pages)) {
    const bytes = bytesOf(source);
    const natural = bytes && imageSize(bytes);
    if (!natural) continue;
    const target = targetSize(natural, box);
    const format = hasAlpha(bytes) ? "png" : "jpeg";
    const becomesJpeg = format === "jpeg" && !isJpeg(bytes);
    if (target.scale > worthwhileShrink && !becomesJpeg) continue;
    const smaller = Buffer.from(await resample(renderer, bytes, target, format));
    if (!becomesJpeg && smaller.length >= bytes.length) continue;
    index += 1;
    const key = `${keyPrefix}${index}`;
    resampled.set(key, smaller);
    box.images.forEach((image) => image.setAttribute("src", key));
  }
  return resampled;
}
