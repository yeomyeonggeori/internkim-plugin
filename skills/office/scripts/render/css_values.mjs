import { splitTopLevel, splitWords } from "./css_parse.mjs";

const namedColors = {
  black: [0, 0, 0], white: [255, 255, 255], red: [255, 0, 0], green: [0, 128, 0], blue: [0, 0, 255], yellow: [255, 255, 0],
  orange: [255, 165, 0], purple: [128, 0, 128], gray: [128, 128, 128], grey: [128, 128, 128], silver: [192, 192, 192],
  navy: [0, 0, 128], teal: [0, 128, 128], maroon: [128, 0, 0], olive: [128, 128, 0], lime: [0, 255, 0], aqua: [0, 255, 255],
  cyan: [0, 255, 255], fuchsia: [255, 0, 255], magenta: [255, 0, 255], pink: [255, 192, 203], brown: [165, 42, 42],
  gold: [255, 215, 0], indigo: [75, 0, 130], violet: [238, 130, 238], crimson: [220, 20, 60], coral: [255, 127, 80],
  tomato: [255, 99, 71], salmon: [250, 128, 114], khaki: [240, 230, 140], beige: [245, 245, 220], ivory: [255, 255, 240],
  lavender: [230, 230, 250], whitesmoke: [245, 245, 245], gainsboro: [220, 220, 220], lightgray: [211, 211, 211],
  lightgrey: [211, 211, 211], darkgray: [169, 169, 169], darkgrey: [169, 169, 169], dimgray: [105, 105, 105],
  slategray: [112, 128, 144], darkblue: [0, 0, 139], darkred: [139, 0, 0], darkgreen: [0, 100, 0], steelblue: [70, 130, 180],
  royalblue: [65, 105, 225], skyblue: [135, 206, 235], tan: [210, 180, 140], chocolate: [210, 105, 30], firebrick: [178, 34, 34],
};
const absoluteFontSizes = { "xx-small": 9, "x-small": 10, small: 13, medium: 16, large: 18, "x-large": 24, "xx-large": 32, "xxx-large": 48 };

export function substituteVariables(value, customProperties, depth = 0) {
  if (!value.includes("var(") || depth > 16) return value;
  const start = value.indexOf("var(");
  let close = start + 4;
  for (let level = 1; close < value.length && level > 0; close += 1) {
    if (value[close] === "(") level += 1;
    if (value[close] === ")") level -= 1;
  }
  const inner = value.slice(start + 4, close - 1);
  const [name, ...fallbackParts] = splitTopLevel(inner, ",");
  const resolved = customProperties.get(name.trim());
  const replacement = resolved !== undefined && resolved !== "" ? resolved : fallbackParts.join(",").trim();
  return substituteVariables(value.slice(0, start) + replacement + value.slice(close), customProperties, depth + 1);
}

function clampByte(value) {
  return Math.max(0, Math.min(255, Math.round(value)));
}

function channel(text, scale) {
  const trimmed = text.trim();
  if (trimmed === "none") return 0;
  return trimmed.endsWith("%") ? (parseFloat(trimmed) / 100) * scale : parseFloat(trimmed);
}

function alphaOf(text) {
  if (text === undefined) return 1;
  return Math.max(0, Math.min(1, channel(text, 1)));
}

function functionArguments(text) {
  const inner = text.slice(text.indexOf("(") + 1, text.lastIndexOf(")"));
  const [main, slashAlpha] = inner.split("/");
  const parts = main.includes(",") ? main.split(",") : main.trim().split(/\s+/);
  return { parts: parts.map((part) => part.trim()), alpha: slashAlpha === undefined ? parts[3] : slashAlpha };
}

function hueToRgb(p, q, t) {
  const hue = t < 0 ? t + 1 : t > 1 ? t - 1 : t;
  if (hue < 1 / 6) return p + (q - p) * 6 * hue;
  if (hue < 1 / 2) return q;
  if (hue < 2 / 3) return p + (q - p) * (2 / 3 - hue) * 6;
  return p;
}

function hslToRgb(hue, saturation, lightness) {
  if (saturation === 0) return [lightness, lightness, lightness].map((value) => value * 255);
  const q = lightness < 0.5 ? lightness * (1 + saturation) : lightness + saturation - lightness * saturation;
  const p = 2 * lightness - q;
  return [hue + 1 / 3, hue, hue - 1 / 3].map((t) => hueToRgb(p, q, t) * 255);
}

function parseHex(text) {
  const digits = text.slice(1);
  const expanded = digits.length <= 4 ? digits.split("").map((digit) => digit + digit).join("") : digits;
  if (!/^[0-9a-f]{6}([0-9a-f]{2})?$/i.test(expanded)) return null;
  const bytes = expanded.match(/../g).map((pair) => parseInt(pair, 16));
  return { red: bytes[0], green: bytes[1], blue: bytes[2], alpha: bytes.length === 4 ? bytes[3] / 255 : 1 };
}

function mixColors(text, currentColor) {
  const [, first, second] = splitTopLevel(text.slice(text.indexOf("(") + 1, text.lastIndexOf(")")), ",").map((part) => part.trim());
  const componentOf = (part) => {
    const percentage = part.match(/\s(\d+(?:\.\d+)?)%$/) || part.match(/^(\d+(?:\.\d+)?)%\s/);
    return { color: parseColor(percentage ? part.replace(percentage[0], " ").trim() : part, currentColor), share: percentage ? parseFloat(percentage[1]) / 100 : null };
  };
  const left = componentOf(first);
  const right = componentOf(second);
  if (!left.color || !right.color) return null;
  const leftShare = left.share ?? (right.share === null ? 0.5 : 1 - right.share);
  const rightShare = right.share ?? 1 - leftShare;
  const total = leftShare + rightShare || 1;
  const alpha = (left.color.alpha * leftShare + right.color.alpha * rightShare) / total;
  const premultiplied = (name) => (left.color[name] * left.color.alpha * leftShare + right.color[name] * right.color.alpha * rightShare) / total;
  const unpremultiply = (name) => (alpha ? premultiplied(name) / alpha : 0);
  return { red: unpremultiply("red"), green: unpremultiply("green"), blue: unpremultiply("blue"), alpha: alpha * Math.min(1, leftShare + rightShare) };
}

export function parseColor(text, currentColor = null) {
  const value = text.trim().toLowerCase();
  if (value === "transparent") return { red: 0, green: 0, blue: 0, alpha: 0 };
  if (value === "currentcolor") return currentColor;
  if (value.startsWith("#")) return parseHex(value);
  if (namedColors[value]) return { red: namedColors[value][0], green: namedColors[value][1], blue: namedColors[value][2], alpha: 1 };
  if (value.startsWith("rgb")) {
    const { parts, alpha } = functionArguments(value);
    return { red: channel(parts[0], 255), green: channel(parts[1], 255), blue: channel(parts[2], 255), alpha: alphaOf(alpha) };
  }
  if (value.startsWith("hsl")) {
    const { parts, alpha } = functionArguments(value);
    const [red, green, blue] = hslToRgb((parseFloat(parts[0]) % 360) / 360, channel(parts[1], 1) / (parts[1].endsWith("%") ? 1 : 100), channel(parts[2], 1) / (parts[2].endsWith("%") ? 1 : 100));
    return { red, green, blue, alpha: alphaOf(alpha) };
  }
  if (value.startsWith("color-mix(")) return mixColors(value, currentColor);
  return null;
}

export function serializeColor(color) {
  const [red, green, blue] = [color.red, color.green, color.blue].map(clampByte);
  if (color.alpha >= 1) return `rgb(${red}, ${green}, ${blue})`;
  return `rgba(${red}, ${green}, ${blue}, ${Math.round(color.alpha * 1000) / 1000})`;
}

export function computeColor(text, currentColor) {
  const color = parseColor(text, currentColor);
  return color ? serializeColor(color) : null;
}

function tokenizeExpression(text) {
  return text.match(/-?\d*\.?\d+(?:e-?\d+)?[a-z%]*|[a-z-]+\(|[()+\-*/,]/gi) || [];
}

function evaluateTokens(tokens, context) {
  let position = 0;
  const primary = () => {
    const token = tokens[position++];
    if (token === "(" || token === "calc(") {
      const value = sum();
      position += 1;
      return value;
    }
    if (token === "min(" || token === "max(" || token === "clamp(") {
      const values = [sum()];
      while (tokens[position] === ",") {
        position += 1;
        values.push(sum());
      }
      position += 1;
      if (token === "min(") return Math.min(...values);
      if (token === "max(") return Math.max(...values);
      return Math.min(Math.max(values[1], values[0]), values[2]);
    }
    if (token === "-") return -primary();
    return lengthOf(token, context);
  };
  const product = () => {
    let value = primary();
    while (tokens[position] === "*" || tokens[position] === "/") {
      const operator = tokens[position++];
      const right = primary();
      value = operator === "*" ? value * right : value / right;
    }
    return value;
  };
  const sum = () => {
    let value = product();
    while (tokens[position] === "+" || tokens[position] === "-") {
      const operator = tokens[position++];
      const right = product();
      value = operator === "+" ? value + right : value - right;
    }
    return value;
  };
  return sum();
}

function lengthOf(token, context) {
  const match = String(token).match(/^(-?\d*\.?\d+(?:e-?\d+)?)([a-z%]*)$/i);
  if (!match) return NaN;
  const number = parseFloat(match[1]);
  const unit = match[2].toLowerCase();
  if (unit === "" || unit === "px") return number;
  if (unit === "em") return number * context.fontSize;
  if (unit === "rem") return number * context.rootFontSize;
  if (unit === "%") return (number / 100) * (context.percentBase ?? NaN);
  if (unit === "pt") return (number * 4) / 3;
  if (unit === "pc") return number * 16;
  if (unit === "in") return number * 96;
  if (unit === "cm") return (number * 96) / 2.54;
  if (unit === "mm") return (number * 96) / 25.4;
  if (unit === "vw") return (number / 100) * context.viewportWidth;
  if (unit === "vh") return (number / 100) * context.viewportHeight;
  if (unit === "ch" || unit === "ex") return number * context.fontSize * 0.5;
  return NaN;
}

export function resolveLength(text, context) {
  const value = text.trim();
  if (/^(calc|min|max|clamp)\(/i.test(value)) return evaluateTokens(tokenizeExpression(value), context);
  return lengthOf(value, context);
}

export function computeFontSize(text, parentFontSize, context) {
  const value = text.trim().toLowerCase();
  if (absoluteFontSizes[value]) return absoluteFontSizes[value];
  if (value === "smaller") return parentFontSize / 1.2;
  if (value === "larger") return parentFontSize * 1.2;
  const size = resolveLength(value, { ...context, fontSize: parentFontSize, percentBase: parentFontSize });
  return Number.isFinite(size) ? size : parentFontSize;
}

export function computeFontWeight(text, parentWeight) {
  const value = text.trim().toLowerCase();
  if (value === "normal") return 400;
  if (value === "bold") return 700;
  if (value === "bolder") return parentWeight < 350 ? 400 : parentWeight < 550 ? 700 : 900;
  if (value === "lighter") return parentWeight < 550 ? 100 : parentWeight < 750 ? 400 : 700;
  const number = parseFloat(value);
  return Number.isFinite(number) ? number : parentWeight;
}

export function isColorWord(word) {
  return parseColor(word) !== null || word.toLowerCase() === "currentcolor";
}

export function wordsOf(text) {
  return splitWords(text.trim());
}
