const generatedAttribute = "data-render-generated";
const hostAttribute = "data-render-pseudo";
const pseudoElements = ["before", "after"];
const replacedTags = new Set(["img", "input", "textarea", "select", "video", "audio", "canvas", "iframe", "object", "embed", "br", "hr"]);

export const generatedContentStyle = `[${hostAttribute}~="before"]::before, [${hostAttribute}~="after"]::after { content: none !important; }`;

function unescapeCssString(text) {
  return text.replace(/\\([0-9a-fA-F]{1,6})\s?/g, (match, hex) => String.fromCodePoint(parseInt(hex, 16))).replace(/\\(.)/g, "$1");
}

function contentText(content, element) {
  const value = content.trim();
  if (value === "none" || value === "normal") return null;
  let text = "";
  for (const part of value.match(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|attr\([^)]*\)|\S+/g) || []) {
    if (/^["']/.test(part)) text += unescapeCssString(part.slice(1, -1));
    else if (part.startsWith("attr(")) text += element.getAttribute(part.slice(5, -1).trim()) ?? "";
    else return null;
  }
  return text;
}

function generatedElement(document, pseudo, text, declarations) {
  const span = document.createElement("span");
  span.setAttribute(generatedAttribute, pseudo);
  span.setAttribute("style", declarations.map((declaration) => `${declaration.property}: ${declaration.value}`).join("; "));
  span.textContent = text;
  return span;
}

function materializeOn(document, element, styles) {
  const hosted = new Set((element.getAttribute(hostAttribute) || "").split(" ").filter(Boolean));
  for (const pseudo of pseudoElements) {
    if (hosted.has(pseudo)) continue;
    const generated = styles.generatedContent(element, pseudo);
    const text = generated ? contentText(generated.content, element) : null;
    if (text === null) continue;
    const span = generatedElement(document, pseudo, text, generated.declarations);
    if (pseudo === "before") element.insertBefore(span, element.firstChild);
    else element.appendChild(span);
    hosted.add(pseudo);
    element.setAttribute(hostAttribute, Array.from(hosted).join(" "));
  }
}

export function materializeGeneratedContent(document, pages, styles) {
  for (const page of pages) {
    for (const element of [page, ...Array.from(page.querySelectorAll("*"))]) {
      if (replacedTags.has(element.localName) || element.closest("svg") || element.hasAttribute(generatedAttribute)) continue;
      materializeOn(document, element, styles);
    }
  }
}
