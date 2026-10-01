import * as CSSselect from "css-select";
import { parseDeclarations, parseStylesheet, specificityOf, splitTopLevel, withoutPseudoElement } from "./css_parse.mjs";
import { computeColor, computeFontSize, computeFontWeight, isColorWord, resolveLength, substituteVariables, wordsOf } from "./css_values.mjs";

const sides = ["top", "right", "bottom", "left"];
const corners = ["top-left", "top-right", "bottom-right", "bottom-left"];
const borderWidthKeywords = { thin: 1, medium: 3, thick: 5 };
const lineStyles = new Set(["none", "hidden", "dotted", "dashed", "solid", "double", "groove", "ridge", "inset", "outset"]);
const listStyleTypes = new Set(["disc", "circle", "square", "decimal", "decimal-leading-zero", "lower-alpha", "upper-alpha", "lower-latin", "upper-latin", "lower-roman", "upper-roman", "none"]);
const flexOrGrid = new Set(["flex", "inline-flex", "grid", "inline-grid"]);
const blockified = { inline: "block", "inline-block": "block", "inline-flex": "flex", "inline-grid": "grid", "inline-table": "table", contents: "contents", "list-item": "list-item", none: "none" };

const userAgentStylesheet = `
html, body, div, section, article, aside, header, footer, main, nav, p, h1, h2, h3, h4, h5, h6, ul, ol, dl, dt, dd, figure, figcaption, blockquote, pre, form, fieldset, hr, address, details, summary, legend { display: block; }
li { display: list-item; }
table { display: table; } thead { display: table-header-group; } tbody { display: table-row-group; } tfoot { display: table-footer-group; }
tr { display: table-row; } td, th { display: table-cell; } caption { display: table-caption; }
head, script, style, template, title, meta, link, noscript, base, [hidden] { display: none; }
b, strong, th, h1, h2, h3, h4, h5, h6 { font-weight: bold; }
em, i, cite, var, dfn, address { font-style: italic; }
h1 { font-size: 2em; } h2 { font-size: 1.5em; } h3 { font-size: 1.17em; } h5 { font-size: 0.83em; } h6 { font-size: 0.67em; }
small, sub, sup { font-size: smaller; } sub { vertical-align: sub; } sup { vertical-align: super; }
th { text-align: center; }
a, u, ins { text-decoration: underline; } s, del, strike { text-decoration: line-through; }
ul { list-style-type: disc; } ol { list-style-type: decimal; }
pre, code, kbd, samp { font-family: monospace; } pre { white-space: pre; }
`;

const properties = {
  display: ["inline", false], position: ["static", false], "z-index": ["auto", false], visibility: ["visible", true],
  opacity: ["1", false], color: ["rgb(0, 0, 0)", true], "-webkit-text-fill-color": ["currentcolor", true],
  "font-family": ["sans-serif", true], "font-size": ["16px", true], "font-weight": ["400", true], "font-style": ["normal", true],
  "line-height": ["normal", true], "letter-spacing": ["normal", true], "text-align": ["start", true], "text-transform": ["none", true],
  "text-decoration-line": ["none", false], "text-shadow": ["none", true], "vertical-align": ["baseline", false],
  "white-space": ["normal", true], "word-break": ["normal", true], "writing-mode": ["horizontal-tb", true],
  "list-style-type": ["disc", true], "list-style-position": ["outside", true],
  "background-color": ["rgba(0, 0, 0, 0)", false], "background-image": ["none", false], "background-clip": ["border-box", false],
  "-webkit-background-clip": ["border-box", false], "box-shadow": ["none", false], filter: ["none", false], "backdrop-filter": ["none", false],
  "mix-blend-mode": ["normal", false], "clip-path": ["none", false], "mask-image": ["none", false], "-webkit-mask-image": ["none", false],
  perspective: ["none", false], transform: ["none", false], isolation: ["auto", false], "object-fit": ["fill", false],
  "overflow-x": ["visible", false], "overflow-y": ["visible", false], "box-sizing": ["content-box", false], content: ["normal", false],
  "outline-style": ["none", false], "outline-width": ["medium", false], "outline-color": ["currentcolor", false],
  "border-collapse": ["separate", true], width: ["auto", false], height: ["auto", false],
  top: ["auto", false], right: ["auto", false], bottom: ["auto", false], left: ["auto", false],
  ...Object.fromEntries(sides.flatMap((side) => [
    [`border-${side}-width`, ["medium", false]], [`border-${side}-style`, ["none", false]], [`border-${side}-color`, ["currentcolor", false]],
    [`padding-${side}`, ["0px", false]], [`margin-${side}`, ["0px", false]],
  ])),
  ...Object.fromEntries(corners.map((corner) => [`border-${corner}-radius`, ["0px", false]])),
};

function camelCase(name) {
  return name.replace(/^-webkit-/, "webkit-").replace(/-([a-z])/g, (match, letter) => letter.toUpperCase());
}

function fourValues(words) {
  const [top, right = top, bottom = top, left = right] = words;
  return [top, right, bottom, left];
}

function borderParts(value) {
  const parts = { width: "medium", style: "none", color: "currentcolor" };
  for (const word of wordsOf(value)) {
    if (lineStyles.has(word.toLowerCase())) parts.style = word.toLowerCase();
    else if (isColorWord(word)) parts.color = word;
    else parts.width = word;
  }
  return parts;
}

function backgroundParts(value) {
  const layers = splitTopLevel(value, ",");
  const images = layers.map((layer) => wordsOf(layer).find((word) => /^(url|[a-z-]*gradient)\(/i.test(word))).filter(Boolean);
  const color = wordsOf(layers[layers.length - 1]).find(isColorWord) || "transparent";
  return { "background-color": color, "background-image": images.length ? images.join(", ") : "none" };
}

const shorthands = {
  margin: (value) => Object.fromEntries(fourValues(wordsOf(value)).map((word, index) => [`margin-${sides[index]}`, word])),
  padding: (value) => Object.fromEntries(fourValues(wordsOf(value)).map((word, index) => [`padding-${sides[index]}`, word])),
  inset: (value) => Object.fromEntries(fourValues(wordsOf(value)).map((word, index) => [sides[index], word])),
  "border-width": (value) => Object.fromEntries(fourValues(wordsOf(value)).map((word, index) => [`border-${sides[index]}-width`, word])),
  "border-style": (value) => Object.fromEntries(fourValues(wordsOf(value)).map((word, index) => [`border-${sides[index]}-style`, word])),
  "border-color": (value) => Object.fromEntries(fourValues(wordsOf(value)).map((word, index) => [`border-${sides[index]}-color`, word])),
  border: (value) => Object.fromEntries(sides.flatMap((side) => Object.entries(borderParts(value)).map(([part, word]) => [`border-${side}-${part}`, word]))),
  ...Object.fromEntries(sides.map((side) => [`border-${side}`, (value) => Object.fromEntries(Object.entries(borderParts(value)).map(([part, word]) => [`border-${side}-${part}`, word]))])),
  "border-radius": (value) => {
    const [horizontal, vertical] = value.split("/").map((part) => fourValues(wordsOf(part)));
    return Object.fromEntries(corners.map((corner, index) => [`border-${corner}-radius`, vertical ? `${horizontal[index]} ${vertical[index]}` : horizontal[index]]));
  },
  outline: (value) => {
    const parts = borderParts(value);
    return { "outline-width": parts.width, "outline-style": parts.style, "outline-color": parts.color };
  },
  background: backgroundParts,
  overflow: (value) => {
    const [horizontal, vertical = horizontal] = wordsOf(value);
    return { "overflow-x": horizontal, "overflow-y": vertical };
  },
  "list-style": (value) => {
    const words = wordsOf(value).map((word) => word.toLowerCase());
    const type = words.find((word) => listStyleTypes.has(word) || word.startsWith('"'));
    const position = words.find((word) => word === "inside" || word === "outside");
    return { ...(type ? { "list-style-type": type } : {}), ...(position ? { "list-style-position": position } : {}) };
  },
  "text-decoration": (value) => {
    const line = wordsOf(value).filter((word) => ["underline", "line-through", "overline", "none"].includes(word.toLowerCase()));
    return { "text-decoration-line": line.length ? line.join(" ") : "none" };
  },
  "word-wrap": () => ({}),
};

function expandDeclaration(property, value) {
  const expand = shorthands[property];
  if (expand) return Object.entries(expand(value));
  if (property === "-webkit-mask") return [["-webkit-mask-image", value]];
  if (property === "mask") return [["mask-image", value]];
  return [[property, value]];
}

function createAdapter() {
  const isTag = (node) => node.nodeType === 1;
  const getChildren = (node) => node.childNodes || [];
  const findAll = (test, nodes) => nodes.flatMap((node) => (isTag(node) ? [...(test(node) ? [node] : []), ...findAll(test, getChildren(node))] : []));
  const findOne = (test, nodes) => {
    for (const node of nodes) {
      if (!isTag(node)) continue;
      if (test(node)) return node;
      const found = findOne(test, getChildren(node));
      if (found) return found;
    }
    return null;
  };
  return {
    isTag,
    getChildren,
    getParent: (node) => node.parentNode,
    getName: (element) => element.localName.toLowerCase(),
    getAttributeValue: (element, name) => element.getAttribute(name) ?? undefined,
    hasAttrib: (element, name) => element.hasAttribute(name),
    getSiblings: (element) => (element.parentNode ? getChildren(element.parentNode) : [element]),
    getText: (node) => node.textContent || "",
    existsOne: (test, nodes) => findOne(test, nodes) !== null,
    findAll,
    findOne,
    removeSubsets: (nodes) => nodes.filter((node, index) => nodes.indexOf(node) === index && !nodes.some((other) => other !== node && other.contains?.(node))),
  };
}

function mediaMatcher(viewportWidth) {
  const featureMatches = (feature) => {
    const match = feature.match(/\(\s*(min|max)-width\s*:\s*([\d.]+)px\s*\)/i);
    if (!match) return true;
    return match[1].toLowerCase() === "min" ? viewportWidth >= parseFloat(match[2]) : viewportWidth <= parseFloat(match[2]);
  };
  return (query) => splitTopLevel(query, ",").some((part) => {
    const text = part.trim().toLowerCase();
    if (/^not\s+print\b/.test(text)) return true;
    if (/^(only\s+)?print\b/.test(text)) return false;
    return (text.match(/\([^)]*\)/g) || []).every(featureMatches);
  });
}

function compileRules(styleTexts, origin, firstOrder, adapter, mediaMatches) {
  let order = firstOrder;
  return styleTexts.flatMap((text) => parseStylesheet(text, mediaMatches).flatMap((rule) => rule.selectors.flatMap((selector) => {
    const { specificity, pseudoElement } = specificityOf(selector);
    let test;
    try {
      test = CSSselect.compile(withoutPseudoElement(selector), { adapter, xmlMode: false });
    } catch {
      return [];
    }
    order += 1;
    return [{ test, specificity, pseudoElement, declarations: rule.declarations, origin, order }];
  })));
}

function priorityOf(entry) {
  return [entry.important ? 1 : 0, entry.important ? -entry.origin : entry.origin, entry.specificity, entry.order];
}

function comparePriority(first, second) {
  const left = priorityOf(first);
  const right = priorityOf(second);
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
}

export function createStyleEngine({ styleTexts, viewport, version, percentBaseOf, ownSizeOf }) {
  const adapter = createAdapter();
  const mediaMatches = mediaMatcher(viewport.width);
  const userAgentRules = compileRules([userAgentStylesheet], 0, 0, adapter, mediaMatches);
  const authorRules = compileRules(styleTexts, 1, 100000, adapter, mediaMatches);
  const rules = [...userAgentRules, ...authorRules];
  const cache = new WeakMap();
  let rootStyle = null;
  rootStyle = computeFrom(null, [], null);

  function matchedDeclarations(element, pseudoElement) {
    const matched = [];
    for (const rule of rules) {
      if (rule.pseudoElement !== pseudoElement) continue;
      let isMatch = false;
      try {
        isMatch = rule.test(element);
      } catch {
        isMatch = false;
      }
      if (!isMatch) continue;
      for (const declaration of rule.declarations) matched.push({ ...declaration, specificity: rule.specificity, origin: rule.origin, order: rule.order });
    }
    if (!pseudoElement) {
      parseDeclarations(element.getAttribute("style") || "").forEach((declaration, index) => matched.push({ ...declaration, specificity: 1e9, origin: 2, order: 1e9 + index }));
    }
    return matched.sort(comparePriority);
  }

  function customPropertiesOf(declarations, parentStyle) {
    const raw = new Map(parentStyle ? parentStyle.customProperties : []);
    for (const declaration of declarations) {
      if (declaration.property.startsWith("--")) raw.set(declaration.property, declaration.value);
    }
    const resolved = new Map();
    for (const [name, value] of raw) resolved.set(name, substituteVariables(value, raw));
    return resolved;
  }

  function specifiedValues(declarations, customProperties) {
    const specified = new Map();
    for (const declaration of declarations) {
      if (declaration.property.startsWith("--")) continue;
      const value = substituteVariables(declaration.value, customProperties);
      for (const [longhand, longhandValue] of expandDeclaration(declaration.property, value)) specified.set(longhand, longhandValue.trim());
    }
    return specified;
  }

  function computeFrom(element, declarations, parentStyle) {
    const customProperties = customPropertiesOf(declarations, parentStyle);
    const specified = specifiedValues(declarations, customProperties);
    const parent = parentStyle || null;
    const valueOf = (name) => {
      const [initial, inherited] = properties[name];
      const declared = specified.get(name);
      const keyword = declared?.toLowerCase();
      if (keyword === "inherit" || ((keyword === "unset" || declared === undefined) && inherited)) return parent ? inheritedValue(parent, name) : initial;
      if (declared === undefined || keyword === "initial" || keyword === "unset") return initial;
      return declared;
    };
    const declaredValues = Object.fromEntries(Object.keys(properties).map((name) => [name, valueOf(name)]));
    return finish(element, declaredValues, customProperties, parent);
  }

  function finish(element, declaredValues, customProperties, parent) {
    const rootFontSize = rootStyle ? rootStyle.fontSizePx : 16;
    const context = { rootFontSize, viewportWidth: viewport.width, viewportHeight: viewport.height };
    const fontSizePx = computeFontSize(declaredValues["font-size"], parent ? parent.fontSizePx : 16, context);
    const lengthContext = { ...context, fontSize: fontSizePx };
    const color = computeColor(declaredValues.color, parent ? parent.colorObject : null) || (parent ? parent.computed.color : "rgb(0, 0, 0)");
    const colorObject = { ...parseColorObject(color) };
    const computed = {};
    for (const [name, value] of Object.entries(declaredValues)) computed[name] = value;
    computed.color = color;
    computed["font-size"] = `${fontSizePx}px`;
    computed["font-weight"] = String(computeFontWeight(declaredValues["font-weight"], parent ? parseFloat(parent.computed["font-weight"]) : 400));
    computed["line-height"] = computeLineHeight(declaredValues["line-height"], lengthContext);
    computed["letter-spacing"] = computeLetterSpacing(declaredValues["letter-spacing"], lengthContext);
    computed["-webkit-text-fill-color"] = computeColor(declaredValues["-webkit-text-fill-color"], colorObject) || color;
    computed["background-color"] = computeColor(declaredValues["background-color"], colorObject) || "rgba(0, 0, 0, 0)";
    computed["outline-color"] = computeColor(declaredValues["outline-color"], colorObject) || color;
    computed["text-align"] = { start: "left", end: "right" }[declaredValues["text-align"]] || declaredValues["text-align"];
    computed.display = displayOf(declaredValues.display, declaredValues.position, parent);
    computed["outline-width"] = `${lineWidth(declaredValues["outline-width"], declaredValues["outline-style"], lengthContext)}px`;
    for (const side of sides) {
      computed[`border-${side}-color`] = computeColor(declaredValues[`border-${side}-color`], colorObject) || color;
      computed[`border-${side}-width`] = `${lineWidth(declaredValues[`border-${side}-width`], declaredValues[`border-${side}-style`], lengthContext)}px`;
      computed[`padding-${side}`] = `${lengthOrZero(declaredValues[`padding-${side}`], element, lengthContext)}px`;
    }
    for (const corner of corners) computed[`border-${corner}-radius`] = computeRadius(declaredValues[`border-${corner}-radius`], lengthContext);
    for (const name of ["top", "right", "bottom", "left", "width", "height"]) computed[name] = computeOffset(declaredValues[name], lengthContext);
    return { element, computed, specified: declaredValues, customProperties, fontSizePx, colorObject, lengthContext };
  }

  function lengthOrZero(value, element, context) {
    const percentBase = element && value.includes("%") ? percentBaseOf(element) : undefined;
    const length = resolveLength(value, { ...context, percentBase });
    return Number.isFinite(length) ? round(length) : 0;
  }

  function styleOf(element) {
    if (!element || element.nodeType !== 1) return rootStyle;
    const currentVersion = version();
    const cached = cache.get(element);
    if (cached && cached.version === currentVersion) return cached.style;
    const parentStyle = element.parentElement ? styleOf(element.parentElement) : rootStyle;
    const style = computeFrom(element, matchedDeclarations(element, ""), parentStyle);
    cache.set(element, { version: currentVersion, style });
    return style;
  }

  function pseudoStyleOf(element, pseudoElement) {
    const elementStyle = styleOf(element);
    if (pseudoElement === "marker") return elementStyle;
    const declarations = matchedDeclarations(element, pseudoElement);
    if (!declarations.length) return { ...elementStyle, computed: { ...elementStyle.computed, content: "none", display: "inline" } };
    return computeFrom(null, declarations, elementStyle);
  }

  function generatedContent(element, pseudoElement) {
    const declarations = matchedDeclarations(element, pseudoElement);
    if (!declarations.length) return null;
    const customProperties = customPropertiesOf(declarations, styleOf(element));
    const resolved = declarations.filter((declaration) => !declaration.property.startsWith("--")).map((declaration) => ({ property: declaration.property, value: substituteVariables(declaration.value, customProperties) }));
    const content = resolved.filter((declaration) => declaration.property === "content").pop()?.value;
    return content ? { content, declarations: resolved.filter((declaration) => declaration.property !== "content") } : null;
  }

  return {
    generatedContent,
    getComputedStyle(element, pseudo) {
      const pseudoElement = (pseudo || "").replace(/^:+/, "").toLowerCase();
      const style = pseudoElement ? pseudoStyleOf(element, pseudoElement) : styleOf(element);
      const view = declarationView(style.computed);
      Object.defineProperty(view, "transform", { enumerable: true, get: () => computeTransform(style.specified.transform, style.lengthContext, pseudoElement ? null : ownSizeOf(element)) });
      return view;
    },
    fontSizeOf: (element) => styleOf(element).fontSizePx,
    displayOf: (element) => styleOf(element).computed.display,
  };
}

function inheritedValue(parentStyle, name) {
  const specified = parentStyle.specified[name];
  if (name === "line-height" && Number.isFinite(Number(specified))) return specified;
  if (specified?.toLowerCase() === "currentcolor") return specified;
  return parentStyle.computed[name];
}

function parseColorObject(serialized) {
  const numbers = serialized.match(/[\d.]+/g).map(Number);
  return { red: numbers[0], green: numbers[1], blue: numbers[2], alpha: numbers[3] ?? 1 };
}

function round(value) {
  return Math.round(value * 1000) / 1000;
}

function computeLineHeight(value, context) {
  if (value === "normal") return "normal";
  const number = Number(value);
  if (Number.isFinite(number)) return `${round(number * context.fontSize)}px`;
  const length = resolveLength(value, { ...context, percentBase: context.fontSize });
  return Number.isFinite(length) ? `${round(length)}px` : "normal";
}

function computeOffset(value, context) {
  if (!value || value === "auto" || value.includes("%")) return value;
  const length = resolveLength(value, context);
  return Number.isFinite(length) ? `${round(length)}px` : value;
}

function computeLetterSpacing(value, context) {
  if (value === "normal") return "normal";
  const length = resolveLength(value, context);
  return Number.isFinite(length) && length !== 0 ? `${round(length)}px` : "normal";
}

function lineWidth(widthValue, styleValue, context) {
  if (styleValue === "none" || styleValue === "hidden") return 0;
  const keyword = borderWidthKeywords[widthValue];
  if (keyword !== undefined) return keyword;
  const length = resolveLength(widthValue, context);
  return Number.isFinite(length) ? round(length) : 0;
}

function computeRadius(value, context) {
  return wordsOf(value).map((word) => {
    if (word.endsWith("%")) return word;
    const length = resolveLength(word, context);
    return `${Number.isFinite(length) ? round(length) : 0}px`;
  }).join(" ");
}

function computeTransform(value, context, size) {
  if (!value || value === "none") return "none";
  let x = 0;
  let y = 0;
  for (const word of wordsOf(value)) {
    const match = word.match(/^(translate|translateX|translateY|translate3d)\((.*)\)$/i);
    if (!match) return value;
    const name = match[1].toLowerCase();
    const percentBases = name === "translatey" ? [size?.height] : [size?.width, size?.height];
    const parts = splitTopLevel(match[2], ",").map((part, index) => resolveLength(part.trim(), { ...context, percentBase: percentBases[index] }));
    if (parts.some((part) => !Number.isFinite(part))) return value;
    if (name === "translatey") y += parts[0];
    else {
      x += parts[0];
      y += name === "translatex" ? 0 : parts[1] ?? 0;
    }
  }
  return `matrix(1, 0, 0, 1, ${round(x)}, ${round(y)})`;
}

function displayOf(display, position, parent) {
  const value = display.toLowerCase();
  const isOutOfFlow = position === "absolute" || position === "fixed";
  if (isOutOfFlow || (parent && flexOrGrid.has(parent.computed.display))) return blockified[value] || value;
  return value;
}

function declarationView(computed) {
  const view = { getPropertyValue: (name) => computed[name] ?? "" };
  for (const [name, value] of Object.entries(computed)) view[camelCase(name)] = value;
  view.borderTopLeftRadius = computed["border-top-left-radius"];
  view.cssFloat = "none";
  view.textDecoration = computed["text-decoration-line"];
  view.backdropFilter = computed["backdrop-filter"];
  view.webkitBackgroundClip = computed["-webkit-background-clip"];
  view.webkitMaskImage = computed["-webkit-mask-image"];
  view.webkitTextFillColor = computed["-webkit-text-fill-color"];
  return view;
}
