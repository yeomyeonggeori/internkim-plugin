import { fromHtml } from "@takumi-rs/helpers/html";
import { createStyleEngine } from "./css_cascade.mjs";

const atomicTags = new Set(["img", "svg", "canvas", "video", "iframe", "object", "embed", "input", "button", "select", "textarea", "math", "audio", "picture"]);
const flexOrGrid = new Set(["flex", "inline-flex", "grid", "inline-grid"]);
const inlineBoxDisplays = new Set(["inline-block", "inline-flex", "inline-grid", "inline-table"]);
const boxOnlyDisplays = new Set(["flex", "inline-flex", "grid", "inline-grid", "table", "inline-table", "table-row-group", "table-header-group", "table-footer-group", "table-row"]);
const resetStyle = "html, body { margin: 0 !important; padding: 0 !important; }";
const emptyRect = { left: 0, top: 0, right: 0, bottom: 0 };
const noInset = emptyRect;

function escapeAttribute(value) {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function openTag(element) {
  const attributes = Array.from(element.attributes).map((attribute) => ` ${attribute.name}="${escapeAttribute(attribute.value)}"`).join("");
  return `<${element.localName}${attributes}>`;
}

function ancestorsOf(element) {
  const chain = [];
  for (let current = element.parentElement; current; current = current.parentElement) chain.unshift(current);
  return chain;
}

export function documentFragmentHtml(elements) {
  const chain = ancestorsOf(elements[0]);
  return `${chain.map(openTag).join("")}${elements.map((element) => element.outerHTML).join("")}${chain.reverse().map((element) => `</${element.localName}>`).join("")}`;
}

function rectFromMeasured(measured, inset = noInset) {
  const [a, b, c, d, e, f] = measured.transform;
  const left = inset.left;
  const top = inset.top;
  const right = Math.max(left, measured.width - inset.right);
  const bottom = Math.max(top, measured.height - inset.bottom);
  const corners = [[left, top], [right, top], [left, bottom], [right, bottom]].map(([x, y]) => [a * x + c * y + e, b * x + d * y + f]);
  const xs = corners.map(([x]) => x);
  const ys = corners.map(([, y]) => y);
  return { left: Math.min(...xs), top: Math.min(...ys), right: Math.max(...xs), bottom: Math.max(...ys) };
}

function domRect(rect) {
  const width = rect.right - rect.left;
  const height = rect.bottom - rect.top;
  return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width, height, x: rect.left, y: rect.top, toJSON: () => ({ ...rect, width, height }) };
}

function union(rects) {
  if (!rects.length) return null;
  return {
    left: Math.min(...rects.map((rect) => rect.left)),
    top: Math.min(...rects.map((rect) => rect.top)),
    right: Math.max(...rects.map((rect) => rect.right)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  };
}

function isWhitespace(character) {
  return /\s/.test(character);
}

export function createLayout({ window, document, renderer, styleTexts, viewport, pageSelector, fontFor, inlineStyles }) {
  let version = 0;
  const observer = new window.MutationObserver(() => {});
  observer.observe(document, { subtree: true, attributes: true, childList: true, characterData: true });
  const currentVersion = () => {
    if (observer.takeRecords().length) version += 1;
    return version;
  };
  patchStyleMutations(document, () => {
    version += 1;
  });
  const layouts = new Map();
  const boxOf = (element) => layoutFor(element)?.boxes.get(element) || null;
  const styles = createStyleEngine({
    styleTexts,
    viewport,
    version: currentVersion,
    percentBaseOf: (element) => {
      const box = element.parentElement ? boxOf(element.parentElement) : null;
      return box ? box.right - box.left : NaN;
    },
    ownSizeOf: (element) => {
      const rect = elementRect(element);
      return rect ? { width: rect.right - rect.left, height: rect.bottom - rect.top } : null;
    },
  });
  const displayOf = (element) => styles.displayOf(element);

  function rootOf(node) {
    let element = node.nodeType === 1 ? node : node.parentElement;
    let page = null;
    let topLevel = element;
    for (let current = element; current; current = current.parentElement) {
      if (current.matches?.(pageSelector)) page = current;
      if (current.parentElement && current.parentElement !== document.body && current.parentElement !== document.documentElement) continue;
      if (current !== document.body && current !== document.documentElement) topLevel = current;
    }
    return page || (topLevel !== document.body && topLevel !== document.documentElement ? topLevel : null);
  }

  function layoutFor(node) {
    const root = rootOf(node);
    return root ? layouts.get(root) || null : null;
  }

  function sizeOf(root) {
    const style = styles.getComputedStyle(root);
    const pixels = (value) => (String(value).endsWith("px") && parseFloat(value) > 0 ? parseFloat(value) : null);
    return { width: pixels(style.width) ?? viewport.width, height: pixels(style.height) ?? viewport.height };
  }

  function pageDocument(root) {
    const size = sizeOf(root);
    const parsed = fromHtml(inlineStyles.filterHtml(documentFragmentHtml([root])));
    return { node: parsed.node, css: [...styleTexts, resetStyle, ...parsed.css], size };
  }

  async function layOut(node) {
    const root = rootOf(node);
    if (!root) return null;
    dropCollapsibleWhitespace(root);
    const stamp = currentVersion();
    const existing = layouts.get(root);
    if (existing && existing.version === stamp) return existing;
    await inlineStyles.prepare([root]);
    const page = pageDocument(root);
    const measured = await renderer.measure(page.node, { width: page.size.width, height: page.size.height, css: page.css });
    const layout = { version: stamp, root, size: page.size, boxes: new Map(), fragments: new Map(), unmapped: [] };
    layouts.set(root, layout);
    mapDocument(measured, root, layout);
    layout.version = currentVersion();
    return layout;
  }

  function isCollapsibleWhitespace(node) {
    if (node.nodeType !== 3 || node.textContent.trim() !== "") return false;
    const parent = node.parentElement;
    if (!parent || styles.getComputedStyle(parent).whiteSpace.startsWith("pre")) return false;
    if (boxOnlyDisplays.has(displayOf(parent))) return textRunOf(node).every((text) => text.textContent.trim() === "");
    return Array.from(parent.childNodes).every((sibling) => (sibling.nodeType === 3 ? sibling.textContent.trim() === "" : sibling.nodeType !== 1 || isBlockLevel(sibling)));
  }

  function textRunOf(node) {
    const run = [node];
    for (let before = node.previousSibling; before && before.nodeType === 3; before = before.previousSibling) run.push(before);
    for (let after = node.nextSibling; after && after.nodeType === 3; after = after.nextSibling) run.push(after);
    return run;
  }

  function dropCollapsibleWhitespace(element) {
    for (const child of Array.from(element.childNodes)) {
      if (isCollapsibleWhitespace(child)) child.remove();
      else if (child.nodeType === 1 && child.localName !== "svg") dropCollapsibleWhitespace(child);
    }
  }

  function mapDocument(measured, root, layout) {
    let measuredNode = measured;
    for (const ancestor of ancestorsOf(root).slice(1)) {
      if (measuredNode.children.length !== 1) return layout.unmapped.push(`${ancestor.localName}: expected one box, found ${measuredNode.children.length}`);
      measuredNode = measuredNode.children[0];
    }
    if (measuredNode.children.length !== 1) return layout.unmapped.push(`page: expected one box, found ${measuredNode.children.length}`);
    mapElement(measuredNode.children[0], root, layout);
  }

  function visibleChildren(nodes) {
    return nodes.flatMap((node) => {
      if (node.nodeType === 3) return [node];
      if (node.nodeType !== 1) return [];
      if (displayOf(node) === "contents") return visibleChildren(Array.from(node.childNodes));
      return [node];
    });
  }

  const isHidden = (node) => node.nodeType === 1 && displayOf(node) === "none";
  const isBlockLevel = (node) => node.nodeType === 1 && (isHidden(node) || (!displayOf(node).startsWith("inline") && displayOf(node) !== "contents"));
  const isAtomicInline = (node) => node.nodeType === 1 && (isHidden(node) || atomicTags.has(node.localName) || inlineBoxDisplays.has(displayOf(node)));
  const hasVisibleText = (node) => node.nodeType === 3 && node.textContent.trim() !== "";

  function inlineAtomicEntries(nodes) {
    return visibleChildren(nodes).flatMap((node) => {
      if (node.nodeType !== 1) return [];
      if (isAtomicInline(node)) return [{ element: node, isInlineLevel: true }];
      return inlineAtomicEntries(Array.from(node.childNodes));
    });
  }

  function inlineTextNodes(nodes) {
    return visibleChildren(nodes).flatMap((node) => {
      if (node.nodeType === 3) return [node];
      if (isHidden(node) || isAtomicInline(node) || node.localName === "br") return [];
      return inlineTextNodes(Array.from(node.childNodes));
    });
  }

  function tableCells(table) {
    const rows = Array.from(table.querySelectorAll("tr")).filter((row) => row.closest("table") === table);
    return rows.flatMap((row) => visibleChildren(Array.from(row.childNodes)).filter((cell) => cell.nodeType === 1)).map((cell) => ({ element: cell }));
  }

  function groupEntries(children) {
    const entries = [];
    let group = [];
    const closeGroup = () => {
      if (group.some((node) => hasVisibleText(node) || node.nodeType === 1)) entries.push({ anonymous: group });
      group = [];
    };
    for (const node of children) {
      if (isBlockLevel(node)) {
        closeGroup();
        entries.push({ element: node });
      } else {
        group.push(node);
      }
    }
    closeGroup();
    return entries;
  }

  function flexEntries(children) {
    const entries = [];
    let textGroup = [];
    const closeText = () => {
      if (textGroup.some(hasVisibleText)) entries.push({ anonymous: textGroup });
      textGroup = [];
    };
    for (const node of children) {
      if (node.nodeType === 3) {
        textGroup.push(node);
        continue;
      }
      closeText();
      entries.push({ element: node });
    }
    closeText();
    return entries;
  }

  function boxEntries(element) {
    if (atomicTags.has(element.localName)) return { entries: [], ownsText: false };
    const display = displayOf(element);
    if (display === "table" || display === "inline-table") return { entries: tableCells(element), ownsText: false };
    const children = visibleChildren(Array.from(element.childNodes));
    if (flexOrGrid.has(display)) return { entries: flexEntries(children), ownsText: false };
    if (children.some(isBlockLevel)) return { entries: groupEntries(children), ownsText: false };
    return { entries: inlineAtomicEntries(children), ownsText: true };
  }

  function hasMarker(element) {
    return displayOf(element) === "list-item" && styles.getComputedStyle(element).listStyleType !== "none";
  }

  function marginsOf(element) {
    const style = styles.getComputedStyle(element);
    const margin = (side) => parseFloat(style[`margin${side}`]) || 0;
    return { left: margin("Left"), top: margin("Top"), right: margin("Right"), bottom: margin("Bottom") };
  }

  function mapElement(measured, element, layout, isInlineLevel = false) {
    if (isHidden(element)) return;
    layout.boxes.set(element, rectFromMeasured(measured, isInlineLevel ? marginsOf(element) : noInset));
    const { entries, ownsText } = boxEntries(element);
    const children = hasMarker(element) && measured.children.length === entries.length + 1 ? measured.children.slice(1) : measured.children;
    if (children.length !== entries.length) {
      layout.unmapped.push(`${describeElement(element)}: predicted ${entries.length} boxes, measured ${children.length}`);
      return;
    }
    if (ownsText) assignRuns(measured, inlineTextNodes(Array.from(element.childNodes)), layout, element);
    entries.forEach((entry, index) => {
      if (entry.element) mapElement(children[index], entry.element, layout, entry.isInlineLevel);
      else mapAnonymous(children[index], entry.anonymous, layout, element);
    });
  }

  function mapAnonymous(measured, nodes, layout, owner) {
    const entries = inlineAtomicEntries(nodes);
    if (measured.children.length !== entries.length) {
      layout.unmapped.push(`${describeElement(owner)} (anonymous): predicted ${entries.length} boxes, measured ${measured.children.length}`);
      return;
    }
    assignRuns(measured, inlineTextNodes(nodes), layout, owner);
    entries.forEach((entry, index) => mapElement(measured.children[index], entry.element, layout, entry.isInlineLevel));
  }

  function assignRuns(measured, textNodes, layout, owner) {
    const runs = measured.runs;
    const origin = rectFromMeasured(measured);
    const characters = textNodes.flatMap((node) => Array.from(node.textContent).map((character, offset) => ({ node, offset, character })).filter((entry) => !isWhitespace(entry.character)));
    let position = 0;
    runs.forEach((run, index) => {
      const next = runs[index + 1];
      const endsLine = !next || Math.abs(next.y - run.y) > 0.5;
      const pieces = [];
      for (const character of Array.from(run.text)) {
        if (isWhitespace(character)) {
          pieces.push({ character, entry: null });
          continue;
        }
        const entry = characters[position];
        if (!entry || entry.character.toUpperCase() !== character.toUpperCase()) {
          layout.unmapped.push(`${describeElement(owner)}: text "${run.text}" does not match the document`);
          position = characters.length;
          return;
        }
        position += 1;
        pieces.push({ character, entry });
      }
      placeRun(run, pieces, endsLine, layout, origin);
    });
  }

  function placeRun(run, pieces, endsLine, layout, origin) {
    const firstEntry = pieces.find((piece) => piece.entry)?.entry;
    if (!firstEntry) return;
    const element = firstEntry.node.parentElement;
    const style = styles.getComputedStyle(element);
    const fontSize = parseFloat(style.fontSize);
    const letterSpacing = style.letterSpacing === "normal" ? 0 : parseFloat(style.letterSpacing);
    const font = fontFor(style.fontFamily, parseFloat(style.fontWeight));
    const advances = pieces.map(({ character }) => (font?.advanceEm(character.codePointAt(0)) ?? 0.5) * fontSize + letterSpacing);
    const total = advances.reduce((sum, advance) => sum + advance, 0) || 1;
    const scale = run.width / total;
    let x = origin.left + run.x;
    const placed = pieces.map((piece, index) => {
      const left = x;
      x += advances[index] * scale;
      return { ...piece, left, right: x };
    });
    const trailing = endsLine ? placed.length - 1 - [...placed].reverse().findIndex((piece) => !isWhitespace(piece.character)) : placed.length - 1;
    const top = origin.top + run.y;
    const bottom = top + run.height;
    for (const piece of placed.slice(0, trailing + 1)) {
      if (!piece.entry) continue;
      const list = layout.fragments.get(piece.entry.node) || [];
      list.push({ offset: piece.entry.offset, left: piece.left, right: piece.right, top, bottom });
      layout.fragments.set(piece.entry.node, list);
    }
  }

  function textRects(node, start = 0, end = Infinity) {
    const fragments = (layoutFor(node)?.fragments.get(node) || []).filter((fragment) => fragment.offset >= start && fragment.offset < end);
    const lines = new Map();
    for (const fragment of fragments) {
      const key = Math.round(fragment.top * 2);
      lines.set(key, union([lines.get(key), fragment].filter(Boolean)));
    }
    return Array.from(lines.values());
  }

  function elementRect(element) {
    const box = boxOf(element);
    if (box) return box;
    const rects = inlineRects(element);
    return union(rects);
  }

  function inlineRects(element) {
    const rects = [];
    for (const node of element.childNodes) {
      if (node.nodeType === 3) rects.push(...textRects(node));
      else if (node.nodeType === 1) {
        const box = boxOf(node);
        if (box) rects.push(box);
        else rects.push(...inlineRects(node));
      }
    }
    return rects;
  }

  function borderWidths(element) {
    const style = styles.getComputedStyle(element);
    return { left: parseFloat(style.borderLeftWidth) || 0, top: parseFloat(style.borderTopWidth) || 0, right: parseFloat(style.borderRightWidth) || 0, bottom: parseFloat(style.borderBottomWidth) || 0 };
  }

  function paddingBox(element) {
    const box = boxOf(element);
    if (!box) return null;
    const borders = borderWidths(element);
    return { left: box.left + borders.left, top: box.top + borders.top, right: box.right - borders.right, bottom: box.bottom - borders.bottom };
  }

  function clips(element) {
    const style = styles.getComputedStyle(element);
    return style.overflowX !== "visible" || style.overflowY !== "visible";
  }

  function descendantEdges(element, end) {
    const edges = [];
    for (const node of element.childNodes) {
      if (node.nodeType === 3) edges.push(...textRects(node).map((rect) => rect[end]));
      if (node.nodeType !== 1) continue;
      const box = boxOf(node);
      if (box) edges.push(box[end]);
      if (!box || !clips(node)) edges.push(...descendantEdges(node, end));
    }
    return edges;
  }

  function inFlowEdges(element, end, marginName) {
    const edges = [];
    for (const node of element.childNodes) {
      if (node.nodeType === 3) edges.push(...textRects(node).map((rect) => rect[end]));
      if (node.nodeType !== 1 || isHidden(node)) continue;
      const box = boxOf(node);
      const style = styles.getComputedStyle(node);
      if (!box) edges.push(...inFlowEdges(node, end, marginName));
      else if (style.position !== "absolute" && style.position !== "fixed") edges.push(box[end] + (parseFloat(style[marginName]) || 0));
    }
    return edges;
  }

  function scrollSize(element, axis) {
    const padding = paddingBox(element);
    if (!padding) return 0;
    const style = styles.getComputedStyle(element);
    const [start, end, paddingEnd, marginName] = axis === "x" ? ["left", "right", style.paddingRight, "marginRight"] : ["top", "bottom", style.paddingBottom, "marginBottom"];
    const client = Math.round(padding[end] - padding[start]);
    const endPadding = parseFloat(paddingEnd) || 0;
    const edges = [...inFlowEdges(element, end, marginName).map((edge) => edge + endPadding), ...descendantEdges(element, end)];
    if (!edges.length) return client;
    return Math.max(client, Math.round(Math.max(...edges) - padding[start]));
  }

  function clientSize(element, axis) {
    const padding = paddingBox(element);
    if (!padding) return 0;
    return Math.round(axis === "x" ? padding.right - padding.left : padding.bottom - padding.top);
  }

  function renderedText(element) {
    if (isHidden(element) || element.localName === "script" || element.localName === "style") return "";
    if (element.localName === "br") return "\n";
    const text = Array.from(element.childNodes).map((node) => (node.nodeType === 3 ? node.textContent.replace(/\s+/g, " ") : node.nodeType === 1 ? renderedText(node) : "")).join("");
    return isBlockLevel(element) ? `\n${text}\n` : text;
  }

  installElementApi(window, { elementRect, inlineRects, boxOf, clientSize, scrollSize, innerText: (element) => renderedText(element).replace(/\n{2,}/g, "\n").trim() });
  installRange(document, textRects);
  return { styles, layOut, layoutFor, rootOf, sizeOf, pageDocument };
}

function describeElement(element) {
  const classes = Array.from(element.classList || []).slice(0, 2).map((name) => `.${name}`).join("");
  return `${element.localName}${classes}`;
}

function patchStyleMutations(document, onChange) {
  const prototype = Object.getPrototypeOf(document.createElement("div").style);
  for (const name of ["setProperty", "removeProperty"]) {
    const original = prototype[name];
    if (typeof original !== "function" || original.patchedForLayout) continue;
    const patched = function (...parameters) {
      onChange();
      return original.apply(this, parameters);
    };
    patched.patchedForLayout = true;
    prototype[name] = patched;
  }
}

function installElementApi(window, layout) {
  const prototypes = [window.Element, window.HTMLElement, window.SVGElement].filter(Boolean).map((type) => type.prototype);
  prototypes.forEach((prototype) => installOn(prototype, layout));
}

function installOn(prototype, layout) {
  const define = (name, get) => Object.defineProperty(prototype, name, { configurable: true, get });
  prototype.getBoundingClientRect = function () {
    return domRect(layout.elementRect(this) || emptyRect);
  };
  prototype.getClientRects = function () {
    const box = layout.boxOf(this);
    return (box ? [box] : layout.inlineRects(this)).map(domRect);
  };
  define("clientWidth", function () {
    return layout.clientSize(this, "x");
  });
  define("clientHeight", function () {
    return layout.clientSize(this, "y");
  });
  define("scrollWidth", function () {
    return layout.scrollSize(this, "x");
  });
  define("scrollHeight", function () {
    return layout.scrollSize(this, "y");
  });
  define("innerText", function () {
    return layout.innerText(this);
  });
  define("offsetWidth", function () {
    const rect = layout.elementRect(this);
    return rect ? Math.round(rect.right - rect.left) : 0;
  });
  define("offsetHeight", function () {
    const rect = layout.elementRect(this);
    return rect ? Math.round(rect.bottom - rect.top) : 0;
  });
}

function installRange(document, textRects) {
  document.createRange = () => {
    const range = { node: null, start: 0, end: Infinity };
    range.selectNodeContents = (node) => Object.assign(range, { node, start: 0, end: Infinity });
    range.setStart = (node, offset) => Object.assign(range, { node, start: offset });
    range.setEnd = (node, offset) => Object.assign(range, { node, end: offset });
    range.getClientRects = () => (range.node && range.node.nodeType === 3 ? textRects(range.node, range.start, range.end).map(domRect) : []);
    range.getBoundingClientRect = () => domRect(union(range.getClientRects()) || emptyRect);
    range.detach = () => {};
    return range;
  };
}
