import fs from "node:fs/promises";
import path from "node:path";
import { fromHtml } from "@takumi-rs/helpers/html";

const pagesPerSheet = 4;
const columns = 2;
const thumbnailWidth = 560;
const padding = 24;
const gutter = 18;
const labelHeight = 34;
const sheetStyle = [
  ".sheet { display: flex; flex-wrap: wrap; gap: 18px; padding: 24px; background: rgb(248, 250, 252); font-family: Paperlogy, sans-serif; }",
  ".page { display: flex; flex-direction: column; }",
  ".badge { align-self: flex-start; height: 26px; padding: 0 10px; margin-bottom: 8px; background: rgba(17, 24, 39, 0.9); color: white; font-size: 18px; font-weight: 700; line-height: 26px; }",
  ".page img { border: 1px solid rgb(203, 213, 225); }",
].join("\n");

function sheetHtml(pages, thumbnailHeight) {
  const cells = pages.map(({ number, png }) => `<div class="page"><div class="badge">${number}</div><img src="data:image/png;base64,${png.toString("base64")}" style="width:${thumbnailWidth}px;height:${thumbnailHeight}px"></div>`);
  return `<div class="sheet">${cells.join("")}</div>`;
}

export async function writeContactSheets(renderer, directory, pages, pageSize) {
  const thumbnailHeight = Math.round((thumbnailWidth * pageSize.height) / pageSize.width);
  const sheetWidth = thumbnailWidth * columns + gutter * (columns - 1) + padding * 2;
  const written = [];
  for (let start = 0; start < pages.length; start += pagesPerSheet) {
    const group = pages.slice(start, start + pagesPerSheet);
    const rows = Math.ceil(group.length / columns);
    const sheetHeight = (thumbnailHeight + labelHeight) * rows + gutter * (rows - 1) + padding * 2;
    const parsed = fromHtml(sheetHtml(group, thumbnailHeight));
    const filename = `contact-sheet-${String(start / pagesPerSheet + 1).padStart(2, "0")}.png`;
    await fs.writeFile(path.join(directory, filename), await renderer.render(parsed.node, { width: sheetWidth, height: sheetHeight, css: [sheetStyle, ...parsed.css], format: "png" }));
    written.push({ filename, slideNumbers: group.map((page) => page.number) });
  }
  return written;
}
