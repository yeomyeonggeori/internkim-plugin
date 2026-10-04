import fs from "node:fs/promises";
import path from "node:path";
import { fromHtml } from "@takumi-rs/helpers/html";

export const nativeIconAttribute = "data-native-icon";

const fallbackScale = 4;

const round = (value) => Math.round(value * 100) / 100;

function hexColor(color) {
  const channels = (color.match(/[\d.]+/g) || ["0", "0", "0"]).slice(0, 3).map((channel) => Math.round(Number(channel)).toString(16).padStart(2, "0"));
  return `#${channels.join("").toUpperCase()}`;
}

function sizedMarkup(svg, color, width, height) {
  return svg.outerHTML.replace(/currentColor/gi, color).replace(/^<svg\b/i, `<svg width="${round(width)}" height="${round(height)}"`);
}

async function pngOf(renderer, svg, color, width, height) {
  const scaledWidth = Math.ceil(width * fallbackScale);
  const scaledHeight = Math.ceil(height * fallbackScale);
  const node = fromHtml(`<div style="display:flex;width:${scaledWidth}px;height:${scaledHeight}px">${sizedMarkup(svg, color, scaledWidth, scaledHeight)}</div>`).node;
  return renderer.render(node, { width: scaledWidth, height: scaledHeight, format: "png" });
}

async function writeIcon(renderer, directory, host, origin, fileStem) {
  const svg = Array.from(host.children).find((child) => child.localName === "svg");
  const rect = svg.getBoundingClientRect();
  const width = rect.right - rect.left;
  const height = rect.bottom - rect.top;
  const color = hexColor(getComputedStyle(host).color);
  await fs.writeFile(path.join(directory, `${fileStem}.svg`), sizedMarkup(svg, color, width, height));
  await fs.writeFile(path.join(directory, `${fileStem}.png`), await pngOf(renderer, svg, color, width, height));
  svg.remove();
  return {
    name: host.getAttribute(nativeIconAttribute),
    box: { left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) },
    svg: `${fileStem}.svg`,
    png: `${fileStem}.png`,
  };
}

function isDrawnIcon(host) {
  const svg = Array.from(host.children).find((child) => child.localName === "svg");
  if (!svg) return false;
  const rect = svg.getBoundingClientRect();
  return rect.right > rect.left && rect.bottom > rect.top;
}

export async function extractNativeIcons({ pages, renderer, directory }) {
  await fs.mkdir(directory, { recursive: true });
  const layouts = [];
  for (const [pageIndex, page] of pages.entries()) {
    const origin = page.getBoundingClientRect();
    const hosts = Array.from(page.querySelectorAll(`[${nativeIconAttribute}]`)).filter(isDrawnIcon);
    const icons = [];
    for (const [iconIndex, host] of hosts.entries()) icons.push(await writeIcon(renderer, directory, host, origin, `icon.${String(pageIndex + 1).padStart(3, "0")}.${iconIndex + 1}`));
    layouts.push({ icons });
  }
  return layouts;
}
