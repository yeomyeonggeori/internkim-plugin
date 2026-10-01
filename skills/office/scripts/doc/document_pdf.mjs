import { readFile, writeFile } from "node:fs/promises";
import { render } from "takumi-pdf";

const request = JSON.parse(await readFile(process.argv[2], "utf8"));
const fonts = await Promise.all(request.fonts.map(async (font) => ({ name: font.family, weight: font.weight, style: "normal", data: await readFile(font.path) })));
const footer = '<div style="display:flex;width:100%;justify-content:center;font-size:8pt;color:#6e7781"><span class="pageNumber"></span>&nbsp;/&nbsp;<span class="totalPages"></span></div>';
const pdf = await render(request.html, {
  size: request.size,
  landscape: request.landscape,
  margin: request.margin,
  css: await readFile(request.cssPath, "utf8"),
  lang: "ko-KR",
  fonts,
  fontFamilies: request.fontFamilies,
  footer,
  outline: true,
  uncoveredText: "placeholder",
  metadata: { title: request.title },
});
await writeFile(request.output, pdf);
