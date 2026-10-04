const linearChannel = (channel) => {
  const share = channel / 255;
  return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
};

export function oklch({ red, green, blue }) {
  const [r, g, b] = [red, green, blue].map(linearChannel);
  const long = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const medium = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const short = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  const lightness = 0.2104542553 * long + 0.793617785 * medium - 0.0040720468 * short;
  const greenRed = 1.9779984951 * long - 2.428592205 * medium + 0.4505937099 * short;
  const blueYellow = 0.0259040371 * long + 0.7827717662 * medium - 0.808675766 * short;
  return { lightness, chroma: Math.hypot(greenRed, blueYellow), hue: ((Math.atan2(blueYellow, greenRed) * 180) / Math.PI + 360) % 360 };
}

const colorPattern = /#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)/g;

export function parseColor(text) {
  const value = String(text).trim();
  const hex = /^#([0-9a-fA-F]{3,8})$/.exec(value);
  if (hex) {
    const digits = hex[1].length <= 4 ? hex[1].split("").map((digit) => digit + digit).join("") : hex[1];
    const channels = digits.match(/../g).map((pair) => parseInt(pair, 16));
    return { red: channels[0], green: channels[1], blue: channels[2], alpha: channels.length > 3 ? channels[3] / 255 : 1 };
  }
  const functional = /^rgba?\(([^)]*)\)$/.exec(value);
  if (!functional) return null;
  const [red, green, blue, alpha = 1] = functional[1].split(/[\s,/]+/).filter(Boolean).map((part) => (part.endsWith("%") ? parseFloat(part) / 100 : parseFloat(part)));
  return { red, green, blue, alpha };
}

const colorsIn = (text) => (String(text || "").match(colorPattern) || []).map(parseColor).filter((color) => color && color.alpha > 0);

const isVisibleColor = (color) => Boolean(color) && color.alpha > 0;

const pixels = (value) => parseFloat(value) || 0;

export function splitTopLevel(text) {
  const parts = [];
  let depth = 0;
  let current = "";
  for (const character of String(text || "")) {
    if (character === "(") depth += 1;
    if (character === ")") depth -= 1;
    if (character === "," && depth === 0) {
      parts.push(current.trim());
      current = "";
      continue;
    }
    current += character;
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
}

const inHueRange = (hue, from, to) => hue >= from && hue <= to;

const sides = ["Top", "Right", "Bottom", "Left"];

const coveringShare = 0.6;

const tableParts = new Set(["TABLE", "THEAD", "TBODY", "TFOOT", "TR", "TD", "TH", "CAPTION", "COLGROUP", "COL"]);

export function measureDesignRules(page, rules, tools) {
  const { describe, isMeasurable, elementsOf, ownTextRects, descendantTextRects, unionRect, slideSize } = tools;
  const styleOf = (element) => getComputedStyle(element);
  const rectOf = (element) => element.getBoundingClientRect();
  const finding = (element, detail) => ({ ...describe(element), detail });
  const fontSize = (element) => pixels(styleOf(element).fontSize);
  const textElements = () => elementsOf(page).filter((element) => ownTextRects(element).length > 0);

  const backgroundOf = (element) => parseColor(styleOf(element).backgroundColor);

  const groundBehind = (element) => {
    for (let current = element.parentElement; current; current = current.parentElement) {
      const color = backgroundOf(current);
      if (isVisibleColor(color)) return color;
    }
    return { red: 255, green: 255, blue: 255, alpha: 1 };
  };

  const sameColor = (first, second) => ["red", "green", "blue"].every((channel) => Math.abs(first[channel] - second[channel]) < 2);

  const borderWidths = (style) => sides.map((side) => (style[`border${side}Style`] === "none" ? 0 : pixels(style[`border${side}Width`])));

  const hasFullBorder = (style) => borderWidths(style).every((width) => width >= 0.5);

  const largestRadius = (element) => {
    const style = styleOf(element);
    const rect = rectOf(element);
    return Math.max(...["TopLeft", "TopRight", "BottomRight", "BottomLeft"].map((corner) => {
      const value = String(style[`border${corner}Radius`] || "0").split(/\s+/)[0];
      return value.endsWith("%") ? (parseFloat(value) / 100) * Math.min(rect.width, rect.height) : pixels(value);
    }));
  };

  const isCard = (element) => {
    if (element === page || tableParts.has(element.tagName.toUpperCase()) || element.closest("svg, figure, table")) return false;
    const style = styleOf(element);
    if (style.display.startsWith("inline")) return false;
    const rect = rectOf(element);
    if (rect.width < 60 || rect.height < 40 || descendantTextRects(element).length === 0) return false;
    const fill = backgroundOf(element);
    const filled = isVisibleColor(fill) && !sameColor(fill, groundBehind(element));
    return filled || hasFullBorder(style);
  };

  const titleOf = () => elementsOf(page).find((element) => ["H1", "H2"].includes(element.tagName.toUpperCase()) && descendantTextRects(element).length > 0);

  const isIcon = (element) => {
    const tag = element.tagName.toUpperCase();
    if (element.classList.contains("kit-icon")) return true;
    if (tag === "SVG" && !element.parentElement.closest("svg") && !element.closest("figure, [data-native-chart]")) return true;
    return tag === "IMG" && Math.max(rectOf(element).width, rectOf(element).height) > 0;
  };

  const tileOf = (icon, maximumIcon) => {
    const parent = icon.parentElement;
    const rect = rectOf(parent);
    const holdsOnlyIcon = parent !== page && parent.children.length === 1 && descendantTextRects(parent).length === 0;
    return holdsOnlyIcon && Math.max(rect.width, rect.height) <= maximumIcon ? parent : icon;
  };

  const overlapsHorizontally = (first, second) => first.left < second.right && second.left < first.right;

  const gradientLayerFindings = (classify) =>
    elementsOf(page).flatMap((element) => {
      const style = styleOf(element);
      const layers = splitTopLevel(style.backgroundImage).filter((layer) => layer.includes("gradient"));
      if (!layers.length) return [];
      const sizes = splitTopLevel(style.backgroundSize);
      const repeats = splitTopLevel(style.backgroundRepeat);
      const rect = rectOf(element);
      const paintedSize = (index) => {
        const lengths = (sizes[index % Math.max(sizes.length, 1)] || "").split(/\s+/).filter((part) => part.endsWith("px")).map(pixels);
        return lengths.length ? { width: lengths[0], height: lengths[1] ?? lengths[0] } : { width: rect.width, height: rect.height };
      };
      const hasSizes = sizes.some((size) => size.includes("px"));
      const reasons = layers.map((layer, index) => classify(layer, paintedSize(index), repeats[index % Math.max(repeats.length, 1)] || "repeat", hasSizes)).filter(Boolean);
      return reasons.length ? [finding(element, reasons[0])] : [];
    });

  const shadowsOf = (element) => {
    const style = styleOf(element);
    return [...splitTopLevel(style.boxShadow), ...splitTopLevel(style.textShadow)].filter((shadow) => shadow && shadow !== "none" && !shadow.includes("inset"));
  };

  const shadowBlur = (shadow) => {
    const lengths = shadow.replace(colorPattern, "").trim().split(/\s+/).filter((part) => /px$|^0$/.test(part)).map(pixels);
    return lengths[2] || 0;
  };

  const measures = {
    canvasFill: ({ tolerance }) => {
      const rect = rectOf(page);
      const isWrong = Math.abs(rect.width - slideSize.width) > tolerance || Math.abs(rect.height - slideSize.height) > tolerance;
      return isWrong ? [finding(page, `drawn ${Math.round(rect.width)}x${Math.round(rect.height)}px on a ${slideSize.width}x${slideSize.height}px canvas`)] : [];
    },

    oneSidedAccentBar: ({ minimumWidth, ratio, stripMaximum, stripShareOfEdge }) => {
      const bordered = elementsOf(page).slice(1).flatMap((element) => {
        const style = styleOf(element);
        const widths = borderWidths(style);
        const widest = Math.max(...widths);
        const side = widths.indexOf(widest);
        if (widest < minimumWidth || widths.some((width, index) => index !== side && width * ratio > widest)) return [];
        const isBox = isVisibleColor(backgroundOf(element)) || largestRadius(element) > 0 || widths.some((width, index) => index !== side && width > 0);
        return isBox ? [finding(element, `a ${widest}px ${sides[side].toLowerCase()} border`)] : [];
      });
      const strips = elementsOf(page).slice(1).flatMap((element) => {
        const host = element.parentElement;
        if (!host || host === page || !isCard(host) || descendantTextRects(element).length > 0 || !isVisibleColor(backgroundOf(element))) return [];
        const rect = rectOf(element);
        const hostRect = rectOf(host);
        const isSideStrip = rect.width <= stripMaximum && rect.height >= hostRect.height * stripShareOfEdge && (Math.abs(rect.left - hostRect.left) <= 2 || Math.abs(rect.right - hostRect.right) <= 2);
        const isEdgeBar = rect.height <= stripMaximum && rect.width >= hostRect.width * stripShareOfEdge && (Math.abs(rect.top - hostRect.top) <= 2 || Math.abs(rect.bottom - hostRect.bottom) <= 2);
        return isSideStrip || isEdgeBar ? [finding(host, `a ${Math.round(Math.min(rect.width, rect.height))}px strip along one edge`)] : [];
      });
      return [...bordered, ...strips];
    },

    extremeRadius: ({ maximum, minimumSide }) =>
      elementsOf(page).filter(isCard).flatMap((element) => {
        const rect = rectOf(element);
        const radius = largestRadius(element);
        const isRound = Math.abs(rect.width - rect.height) <= 2 && radius >= rect.width / 2 - 1;
        return Math.min(rect.width, rect.height) >= minimumSide && radius > maximum && !isRound ? [finding(element, `${Math.round(radius)}px corners`)] : [];
      }),

    labelAboveHeading: ({ sizeShare, reach, maximumCharacters }) => {
      const headings = textElements().filter((element) => /^H[1-4]$/.test(element.tagName.toUpperCase()));
      return headings.flatMap((heading) => {
        const headingRect = unionRect(ownTextRects(heading));
        const headingSize = fontSize(heading);
        return textElements()
          .filter((element) => !heading.contains(element) && !element.contains(heading))
          .filter((element) => !/^H[1-4]$/.test(element.tagName.toUpperCase()) || fontSize(element) <= headingSize * sizeShare)
          .filter((element) => fontSize(element) <= headingSize * sizeShare && (element.textContent || "").trim().length <= maximumCharacters)
          .filter((element) => {
            const rect = unionRect(ownTextRects(element));
            return rect.bottom <= headingRect.top + 2 && rect.bottom >= headingRect.top - reach * headingSize && overlapsHorizontally(rect, headingRect);
          })
          .map((element) => finding(element, `above ${describe(heading).selector}`));
      });
    },

    iconAboveHeading: ({ maximumIcon, reach, headingWeight }) => {
      const headings = textElements().filter((element) => /^H[1-4]$/.test(element.tagName.toUpperCase()) || parseInt(styleOf(element).fontWeight, 10) >= headingWeight);
      return elementsOf(page).slice(1).filter(isIcon).flatMap((icon) => {
        const tile = tileOf(icon, maximumIcon);
        const rect = rectOf(tile);
        if (Math.max(rect.width, rect.height) > maximumIcon || rect.width === 0) return [];
        const heading = headings.find((candidate) => {
          if (candidate.contains(icon)) return false;
          const text = unionRect(ownTextRects(candidate));
          return text.top >= rect.bottom - 2 && text.top - rect.bottom <= reach * fontSize(candidate) && overlapsHorizontally(rect, text);
        });
        return heading ? [finding(tile, `stacked above ${describe(heading).selector}`)] : [];
      });
    },

    identicalCardGrid: ({ minimumCards, sizeTolerance }) => {
      const signature = (element) => Array.from(element.children).map((child) => `${child.tagName}${isIcon(child) || child.querySelector(".kit-icon, svg, img") ? "*" : ""}`).join(" ");
      const sizeKey = (element) => `${Math.round(rectOf(element).width / sizeTolerance)}x${Math.round(rectOf(element).height / sizeTolerance)}`;
      return elementsOf(page).flatMap((parent) => {
        const cards = Array.from(parent.children).filter((child) => isMeasurable(child) && isCard(child));
        const groups = new Map();
        cards.forEach((card) => {
          const key = `${signature(card)}|${sizeKey(card)}`;
          groups.set(key, [...(groups.get(key) || []), card]);
        });
        return Array.from(groups.values())
          .filter((group) => group.length >= minimumCards)
          .map((group) => finding(group[0], `${group.length} cards share one structure and size`));
      });
    },

    nestedCard: () =>
      elementsOf(page).filter(isCard).flatMap((element) => {
        for (let current = element.parentElement; current && current !== page; current = current.parentElement) {
          if (isCard(current)) return [finding(element, `inside ${describe(current).selector}`)];
        }
        return [];
      }),

    gradientText: () =>
      elementsOf(page).flatMap((element) => {
        const style = styleOf(element);
        const clip = `${style.backgroundClip || ""} ${style.webkitBackgroundClip || ""}`;
        return clip.includes("text") && String(style.backgroundImage).includes("gradient") ? [finding(element, "gradient-filled text")] : [];
      }),

    glassBlur: () =>
      elementsOf(page).flatMap((element) => {
        const style = styleOf(element);
        const filter = `${style.backdropFilter || ""} ${style.webkitBackdropFilter || ""}`.trim();
        return filter && !/^(none\s*)+$/.test(filter) ? [finding(element, `backdrop-filter: ${filter}`)] : [];
      }),

    gridStripeBackground: ({ gridTileMaximum }) => gradientLayerFindings((layer, size, repeat, hasSizes) => {
      if (layer.startsWith("repeating-")) return "repeating stripes";
      const isTiledLine = layer.startsWith("linear-gradient") && !repeat.includes("no-repeat") && Math.min(size.width, size.height) <= gridTileMaximum && hasSizes;
      return isTiledLine ? "a grid of lines" : "";
    }),

    radialHalo: ({ radialMinimum }) => gradientLayerFindings((layer, size) => (layer.startsWith("radial-gradient") && Math.min(size.width, size.height) >= radialMinimum ? "a radial halo" : "")),

    glowShadow: ({ glowBlurMinimum, glowChromaMinimum }) =>
      elementsOf(page).flatMap((element) => {
        const glow = shadowsOf(element).flatMap((shadow) => {
          const [color] = colorsIn(shadow);
          return color && shadowBlur(shadow) >= glowBlurMinimum && color.alpha >= 0.15 && oklch(color).chroma >= glowChromaMinimum ? ["a colored glow"] : [];
        });
        return glow.length ? [finding(element, glow[0])] : [];
      }),

    hairlineWideShadow: ({ hairlineMaximum, wideBlurMinimum }) =>
      elementsOf(page).flatMap((element) => {
        const isHairline = borderWidths(styleOf(element)).every((width) => width > 0 && width <= hairlineMaximum);
        const isWide = shadowsOf(element).some((shadow) => shadowBlur(shadow) >= wideBlurMinimum);
        return isHairline && isWide ? [finding(element, "a wide shadow under a hairline border")] : [];
      }),

    tightTracking: ({ minimumEm }) =>
      textElements().flatMap((element) => {
        const style = styleOf(element);
        const spacing = String(style.letterSpacing || "normal");
        const tracking = spacing === "normal" ? 0 : spacing.endsWith("em") ? parseFloat(spacing) : pixels(spacing) / Math.max(fontSize(element), 1);
        return tracking < minimumEm - 0.0005 ? [finding(element, `letter-spacing ${tracking.toFixed(3)}em`)] : [];
      }),

    italicSerifDisplay: ({ serifFamilies = [] }) => {
      const title = titleOf();
      if (!title || !/italic|oblique/.test(styleOf(title).fontStyle)) return [];
      const families = String(styleOf(title).fontFamily).split(",").map((family) => family.trim().replace(/^["']|["']$/g, "").toLowerCase());
      const isSerif = families.some((family) => family === "serif" || serifFamilies.some((serif) => serif.toLowerCase() === family));
      return isSerif ? [finding(title, "italic serif")] : [];
    },

    oversizedTitle: ({ maximumShareOfHeight }) => {
      const title = titleOf();
      const limit = slideSize.height * maximumShareOfHeight;
      return title && fontSize(title) > limit ? [finding(title, `${Math.round(fontSize(title))}px, over ${Math.round(limit)}px`)] : [];
    },

    flatHierarchy: ({ minimumRatio }) => {
      const title = titleOf();
      if (!title) return [];
      const body = textElements().filter((element) => !title.contains(element) && !element.closest("aside"));
      const weighted = body.flatMap((element) => Array((element.textContent || "").trim().length).fill(fontSize(element))).sort((first, second) => first - second);
      if (weighted.length < 20) return [];
      const median = weighted[Math.floor(weighted.length / 2)];
      const ratio = fontSize(title) / median;
      return ratio < minimumRatio ? [finding(title, `title ${Math.round(fontSize(title))}px over body ${Math.round(median)}px`)] : [];
    },

    creamGround: ({ lightnessMinimum, chromaMinimum, hueFrom, hueTo }) => {
      const pageRect = rectOf(page);
      const covering = elementsOf(page).slice(1).filter((element) => {
        const rect = rectOf(element);
        return isVisibleColor(backgroundOf(element)) && backgroundOf(element).alpha >= 0.95 && rect.width * rect.height >= pageRect.width * pageRect.height * coveringShare;
      });
      const grounds = [page, ...covering].map((element) => [element, isVisibleColor(backgroundOf(element)) ? backgroundOf(element) : groundBehind(element)]);
      return grounds.flatMap(([element, ground]) => {
        const { lightness, chroma, hue } = oklch(ground);
        return lightness >= lightnessMinimum && chroma >= chromaMinimum && inHueRange(hue, hueFrom, hueTo) ? [finding(element, `ground ${styleOf(element).backgroundColor}`)] : [];
      });
    },

    aiPalette: ({ purpleHueFrom, purpleHueTo, cyanHueFrom, cyanHueTo, chromaMinimum, darkGroundMaximum }) => {
      const isPurple = (color) => oklch(color).chroma >= chromaMinimum && inHueRange(oklch(color).hue, purpleHueFrom, purpleHueTo);
      const gradients = elementsOf(page).flatMap((element) => {
        const image = String(styleOf(element).backgroundImage);
        return image.includes("gradient") && colorsIn(image).some(isPurple) ? [finding(element, "a purple gradient")] : [];
      });
      const cyan = textElements().flatMap((element) => {
        const color = parseColor(styleOf(element).color);
        const shade = color && oklch(color);
        const isCyan = shade && shade.chroma >= chromaMinimum && inHueRange(shade.hue, cyanHueFrom, cyanHueTo);
        return isCyan && oklch(groundBehind(element)).lightness <= darkGroundMaximum ? [finding(element, "cyan type on a dark ground")] : [];
      });
      return [...gradients, ...cyan.slice(0, 1)];
    },

    emDashes: ({ maximumPerSlide }) => {
      const count = (page.textContent.match(/—/g) || []).length;
      return count > maximumPerSlide ? [finding(page, `${count} em dashes`)] : [];
    },
  };

  return rules.flatMap((rule) => measures[rule.measure](rule.threshold).map((found) => ({ code: rule.code, ...found })));
}

