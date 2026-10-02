import { fromHtml } from "@takumi-rs/helpers/html";
import { parseDeclarations } from "./css_parse.mjs";

const styleAttributePattern = / style="([^"]*)"/g;

function unescapeAttribute(value) {
  return value.replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function declarationText(declaration) {
  return `${declaration.property}: ${declaration.value}${declaration.important ? " !important" : ""}`;
}

function styledElements(elements) {
  const found = new Set();
  for (const element of elements) {
    for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) found.add(ancestor);
    element.querySelectorAll("[style]").forEach((descendant) => found.add(descendant));
  }
  return Array.from(found).filter((element) => element.getAttribute?.("style"));
}

export function createInlineStyleFilter(renderer) {
  const verdicts = new Map();
  const dropped = new Set();

  async function accepts(declaration) {
    try {
      const parsed = fromHtml(`<div style="${escapeAttribute(declarationText(declaration))}"></div>`);
      await renderer.measure(parsed.node, { width: 1, height: 1 });
      return true;
    } catch {
      return false;
    }
  }

  async function prepare(elements) {
    for (const element of styledElements(elements)) {
      for (const declaration of parseDeclarations(element.getAttribute("style"))) {
        const key = declarationText(declaration);
        if (!verdicts.has(key)) verdicts.set(key, await accepts(declaration));
      }
    }
  }

  function filterStyle(styleText) {
    const kept = parseDeclarations(styleText).filter((declaration) => {
      const key = declarationText(declaration);
      if (verdicts.get(key) !== false) return true;
      dropped.add(key);
      return false;
    });
    return kept.map(declarationText).join("; ");
  }

  return {
    prepare,
    filterHtml: (html) => html.replace(styleAttributePattern, (match, value) => ` style="${escapeAttribute(filterStyle(unescapeAttribute(value)))}"`),
    dropped: () => Array.from(dropped),
  };
}
