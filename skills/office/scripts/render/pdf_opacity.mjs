import { parseColor, serializeColor } from "./css_values.mjs";

const foldedColorProperties = ["color", "-webkit-text-fill-color", "background-color", "outline-color", "border-top-color", "border-right-color", "border-bottom-color", "border-left-color"];
const pictureTags = new Set(["img", "svg", "canvas", "video", "picture", "iframe"]);
const groupOnlyEffects = [
  ["background-image", "none"], ["box-shadow", "none"], ["text-shadow", "none"], ["filter", "none"], ["backdrop-filter", "none"],
  ["mix-blend-mode", "normal"], ["clip-path", "none"], ["mask-image", "none"], ["-webkit-mask-image", "none"],
];

function ownOpacity(style) {
  const value = parseFloat(style.getPropertyValue("opacity"));
  return Number.isNaN(value) ? 1 : value;
}

function needsOwnGroup(element, style) {
  if (pictureTags.has(element.tagName.toLowerCase())) return true;
  return groupOnlyEffects.some(([property, unset]) => (style.getPropertyValue(property) || unset) !== unset);
}

function fadedColors(style, factor) {
  const textColor = parseColor(style.getPropertyValue("color"));
  return foldedColorProperties.flatMap((property) => {
    const color = parseColor(style.getPropertyValue(property), textColor);
    if (!color || color.alpha <= 0) return [];
    return [[property, serializeColor({ ...color, alpha: color.alpha * factor })]];
  });
}

function plannedDeclarations(element, styles, inheritedFactor) {
  const style = styles.getComputedStyle(element);
  const factor = inheritedFactor * ownOpacity(style);
  const children = (childFactor) => Array.from(element.children).flatMap((child) => plannedDeclarations(child, styles, childFactor));
  if (factor >= 1) return children(1);
  if (needsOwnGroup(element, style)) return [{ element, declarations: [["opacity", String(Math.round(factor * 1000) / 1000)]] }];
  const declarations = [...(ownOpacity(style) < 1 ? [["opacity", "1"]] : []), ...fadedColors(style, factor)];
  return [{ element, declarations }, ...children(factor)];
}

function declarationsText(declarations) {
  return declarations.map(([property, value]) => `${property}: ${value} !important`).join("; ");
}

export function foldOpacityIntoPaint(pages, styles) {
  const plans = pages.flatMap((page) => plannedDeclarations(page, styles, 1)).filter((plan) => plan.declarations.length);
  const originals = plans.map(({ element }) => ({ element, style: element.getAttribute("style") }));
  for (const { element, declarations } of plans) {
    const existing = element.getAttribute("style");
    element.setAttribute("style", existing ? `${existing}; ${declarationsText(declarations)}` : declarationsText(declarations));
  }
  return () => {
    for (const { element, style } of originals) {
      if (style === null) element.removeAttribute("style");
      else element.setAttribute("style", style);
    }
  };
}
