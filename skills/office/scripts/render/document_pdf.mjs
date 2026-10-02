import { readFile, writeFile } from "node:fs/promises";
import { render } from "takumi-pdf";

async function main() {
  const request = JSON.parse(await readFile(process.argv[2], "utf8"));
  const fonts = await Promise.all(request.fonts.map(async (font) => ({ name: font.family, weight: font.weight, style: font.style || "normal", data: await readFile(font.path), ...(font.generic ? { generic: font.generic } : {}) })));
  const pdf = await render(request.html, {
    size: request.size,
    landscape: request.landscape,
    margin: request.margin,
    css: request.css,
    lang: "ko-KR",
    fonts,
    fontFamilies: request.fontFamilies,
    footer: request.footer || false,
    outline: true,
    uncoveredText: "placeholder",
    metadata: { title: request.title },
  });
  await writeFile(request.output, pdf);
  process.stdout.write(`${JSON.stringify({ pdf: request.output })}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
