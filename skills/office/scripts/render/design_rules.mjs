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

const isVisibleColor = (color) => Boolean(color) && color.alpha > 0;

const pixels = (value) => parseFloat(value) || 0;

const sides = ["Top", "Right", "Bottom", "Left"];

const tableParts = new Set(["TABLE", "THEAD", "TBODY", "TFOOT", "TR", "TD", "TH", "CAPTION", "COLGROUP", "COL"]);

import { measureInkBoxes } from "./ink_boxes.mjs";

const sameColor = (first, second) => ["red", "green", "blue"].every((channel) => Math.abs(first[channel] - second[channel]) < 2);

const borderWidths = (style) => sides.map((side) => (style[`border${side}Style`] === "none" ? 0 : pixels(style[`border${side}Width`])));

const hasFullBorder = (style) => borderWidths(style).every((width) => width >= 0.5);

const areaOf = (rect) => Math.max(0, rect.width) * Math.max(0, rect.height);

function boxReader(page, tools) {
  const { descendantTextRects } = tools;
  const styleOf = (element) => getComputedStyle(element);
  const rectOf = (element) => element.getBoundingClientRect();
  const backgroundOf = (element) => parseColor(styleOf(element).backgroundColor);

  const groundBehind = (element) => {
    for (let current = element.parentElement; current; current = current.parentElement) {
      const color = backgroundOf(current);
      if (isVisibleColor(color)) return color;
    }
    return { red: 255, green: 255, blue: 255, alpha: 1 };
  };

  const isFilled = (element) => {
    const fill = backgroundOf(element);
    return isVisibleColor(fill) && !sameColor(fill, groundBehind(element));
  };

  const isPainted = (element) => {
    const style = styleOf(element);
    return isFilled(element) || (style.backgroundImage && style.backgroundImage !== "none") || borderWidths(style).some((width) => width >= 0.5);
  };

  const readsAsBox = (element) => {
    const style = styleOf(element);
    return isFilled(element) || (style.backgroundImage && style.backgroundImage !== "none") || hasFullBorder(style);
  };

  const isCard = (element) => {
    if (element === page || tableParts.has(element.tagName.toUpperCase()) || element.closest("svg, figure, table")) return false;
    const style = styleOf(element);
    if (style.display.startsWith("inline")) return false;
    const rect = rectOf(element);
    if (rect.width < 60 || rect.height < 40 || descendantTextRects(element).length === 0) return false;
    return isFilled(element) || hasFullBorder(style);
  };

  const shownParts = () => tools.elementsOf(page).slice(1).filter((element) => !element.closest("aside"));

  return { styleOf, rectOf, backgroundOf, isPainted, readsAsBox, isCard, shownParts };
}

export function measureDesignRules(page, rules, tools) {
  const { describe, elementsOf, ownTextRects, descendantTextRects, slideSize, backgroundShareOfSlide } = tools;
  const { styleOf, rectOf, backgroundOf, isPainted, readsAsBox, isCard, shownParts } = boxReader(page, tools);
  const finding = (element, detail) => ({ ...describe(element), detail });
  const fontSize = (element) => pixels(styleOf(element).fontSize);
  const textElements = () => elementsOf(page).filter((element) => ownTextRects(element).length > 0);

  const largestRadius = (element) => {
    const style = styleOf(element);
    const rect = rectOf(element);
    return Math.max(...["TopLeft", "TopRight", "BottomRight", "BottomLeft"].map((corner) => {
      const value = String(style[`border${corner}Radius`] || "0").split(/\s+/)[0];
      return value.endsWith("%") ? (parseFloat(value) / 100) * Math.min(rect.width, rect.height) : pixels(value);
    }));
  };

  const drawnBoxes = (isBox = isPainted) => {
    const pageArea = areaOf(rectOf(page));
    return shownParts()
      .filter((element) => element.matches("img, svg, canvas, video, figure, table") || (isBox(element) && areaOf(rectOf(element)) < pageArea * backgroundShareOfSlide))
      .map(rectOf)
      .filter((rect) => rect.width > 0 && rect.height > 0);
  };

  const isRule = (rect, ruleMaximum) => Math.min(rect.width, rect.height) <= ruleMaximum;

  const fillingBoxes = (ruleMaximum) => drawnBoxes(readsAsBox).filter((rect) => !isRule(rect, ruleMaximum));

  const fillingRects = (ruleMaximum) => [...shownParts().flatMap((element) => ownTextRects(element)), ...fillingBoxes(ruleMaximum)];

  const contentRects = (container) => [
    ...descendantTextRects(container),
    ...Array.from(container.querySelectorAll("img, svg, canvas, video, figure, table")).map(rectOf),
  ].filter((rect) => rect.width > 0 && rect.height > 0);

  const innerBox = (element) => {
    const style = styleOf(element);
    const rect = rectOf(element);
    const top = rect.top + pixels(style.borderTopWidth) + pixels(style.paddingTop);
    const bottom = rect.bottom - pixels(style.borderBottomWidth) - pixels(style.paddingBottom);
    return { top, bottom, height: Math.max(0, bottom - top) };
  };

  const emptyHeightOf = (container) => {
    const inner = innerBox(container);
    const rects = contentRects(container).map((rect) => ({ top: Math.max(inner.top, rect.top), bottom: Math.min(inner.bottom, rect.bottom) })).filter((span) => span.bottom > span.top);
    if (rects.length === 0 || inner.height === 0) return null;
    const extent = Math.max(...rects.map((span) => span.bottom)) - Math.min(...rects.map((span) => span.top));
    return { empty: inner.height - extent, height: inner.height };
  };

  const widestEmptyBand = (rects, frame) => {
    const spans = rects
      .map((rect) => ({ top: Math.max(0, rect.top - frame.top), bottom: Math.min(frame.height, rect.bottom - frame.top) }))
      .filter((span) => span.bottom > span.top)
      .sort((first, second) => first.top - second.top);
    if (spans.length === 0) return null;
    let reached = spans[0].top;
    let widest = { top: reached, bottom: reached };
    for (const span of [...spans, { top: frame.height, bottom: frame.height }]) {
      if (span.top - reached > widest.bottom - widest.top) widest = { top: reached, bottom: span.top };
      reached = Math.max(reached, span.bottom);
    }
    return widest;
  };

  const describeBand = (band, height) => {
    const share = `${Math.round(((band.bottom - band.top) / height) * 100)}%`;
    if (band.bottom >= height) return `everything drawn ends ${Math.round(band.top)}px down the ${Math.round(height)}px page, so its lowest ${Math.round(band.bottom - band.top)}px (${share}) hold nothing`;
    return `nothing is drawn from ${Math.round(band.top)}px to ${Math.round(band.bottom)}px down the ${Math.round(height)}px page, a ${Math.round(band.bottom - band.top)}px band (${share}) empty across its whole width`;
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
        const isSideRule = (side === 1 || side === 3) && descendantTextRects(element).length > 0;
        const isBox = isSideRule || isVisibleColor(backgroundOf(element)) || largestRadius(element) > 0 || widths.some((width, index) => index !== side && width > 0);
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

    brokenWord: ({ maximumCharacters }) =>
      textElements().flatMap((element) =>
        Array.from(element.childNodes)
          .filter((node) => node.nodeType === Node.TEXT_NODE)
          .flatMap((node) =>
            Array.from(node.textContent.matchAll(/\S+/g))
              .filter((word) => word[0].length >= 2 && word[0].length <= maximumCharacters && !/[\u3000-\u9fff\uac00-\ud7af]/.test(word[0]))
              .filter((word) => {
                const range = document.createRange();
                range.setStart(node, word.index);
                range.setEnd(node, word.index + word[0].length);
                const lines = new Set(Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0).map((rect) => Math.round(rect.top / Math.max(fontSize(element) / 2, 1))));
                return lines.size > 1;
              })
              .map((word) => finding(element, `"${word[0]}" is split across two lines`)),
          ),
      ),

    chartCollapsed: ({ minimumHeight, minimumWidth }) =>
      Array.from(page.querySelectorAll("figure[data-chart]")).flatMap((figure) => {
        const box = rectOf(figure);
        return box.height < minimumHeight || box.width < minimumWidth ? [finding(figure, `a chart drawn ${Math.round(box.width)}x${Math.round(box.height)}px, too small to show its marks`)] : [];
      }),

    lowerBand: ({ maximumImbalance, pageTypes }) => {
      if (!pageTypes.includes(page.dataset.type || "")) return [];
      const pageRect = rectOf(page);
      const shown = elementsOf(page).slice(1).filter((element) => !element.closest("aside"));
      const textRects = shown.flatMap((element) => ownTextRects(element));
      const mediaRects = shown.filter((element) => element.matches("img, canvas, video, figure, table")).map(rectOf);
      const drawn = [...textRects, ...mediaRects].filter((rect) => rect.width > 0 && rect.height > 0);
      if (drawn.length === 0) return [];
      const top = Math.max(0, Math.min(...drawn.map((rect) => rect.top - pageRect.top)));
      const lowest = Math.min(pageRect.height, Math.max(...drawn.map((rect) => rect.bottom - pageRect.top)));
      const band = pageRect.height - lowest;
      const boxesEnd = Math.max(lowest, ...drawnBoxes().map((rect) => rect.bottom - pageRect.top));
      const isBandBoxed = boxesEnd - lowest > band / 2;
      return band - top > maximumImbalance && isBandBoxed ? [finding(page, `the last text or picture ends ${Math.round(lowest)}px down the ${Math.round(pageRect.height)}px page, so the ${Math.round(band)}px under it hold nothing to read, against ${Math.round(top)}px above the first`)] : [];
    },

    verticalFill: ({ maximumEmptyShare, ruleMaximum, pageTypes }) => {
      if (!pageTypes.includes(page.dataset.type || "")) return [];
      const frame = rectOf(page);
      const band = widestEmptyBand(fillingRects(ruleMaximum), frame);
      if (!band || band.bottom - band.top <= frame.height * maximumEmptyShare) return [];
      return [finding(page, describeBand(band, frame.height))];
    },

    cardFill: ({ maximumEmptyShare, minimumEmptyHeight, pageTypes }) => {
      if (!pageTypes.includes(page.dataset.type || "")) return [];
      const pageArea = areaOf(rectOf(page));
      return shownParts()
        .filter((element) => isCard(element) && styleOf(element).backgroundImage === "none" && areaOf(rectOf(element)) < pageArea * backgroundShareOfSlide)
        .flatMap((card) => {
          const measured = emptyHeightOf(card);
          if (!measured || measured.empty < minimumEmptyHeight || measured.empty <= measured.height * maximumEmptyShare) return [];
          return [finding(card, `its words and pictures take ${Math.round(measured.height - measured.empty)}px of its ${Math.round(measured.height)}px inner height, leaving ${Math.round(measured.empty)}px (${Math.round((measured.empty / measured.height) * 100)}%) of the box empty`)];
        });
    },

    inkBoxes: (threshold) => measureInkBoxes(page, { describe, elementsOf, ownTextRects, isPainted }, threshold),

    textSize: ({ bodyMinimum, captionMinimum, bodyCharacters, bodyWords }) => {
      const isChartText = (element) => element.closest("svg, figure[data-chart], [data-native-chart]");
      const ownText = (element) => Array.from(element.childNodes).filter((node) => node.nodeType === Node.TEXT_NODE).map((node) => node.textContent.trim()).join(" ").trim();
      const isBody = (element) => {
        const text = ownText(element);
        return ["LI", "TD", "DD", "BLOCKQUOTE"].includes(element.tagName.toUpperCase()) || text.length >= bodyCharacters || text.split(/\s+/).length >= bodyWords;
      };
      return textElements().filter((element) => !isChartText(element)).flatMap((element) => {
        const minimum = isBody(element) ? bodyMinimum : captionMinimum;
        return fontSize(element) < minimum - 0.01 ? [finding(element, `${Math.round(fontSize(element) * 10) / 10}px, under ${minimum}px for ${isBody(element) ? "body text" : "a caption or label"}`)] : [];
      });
    },
  };

  const findings = rules.flatMap((rule) => measures[rule.measure](rule.threshold).map((found) => ({ code: rule.code, ...found })));
  const superseded = new Set(rules.filter((rule) => findings.some((found) => found.code === rule.code)).flatMap((rule) => rule.supersedes || []));
  return findings.filter((found) => !superseded.has(found.code));
}

const isNear = (first, second, tolerance) => Math.abs(first - second) <= tolerance * Math.max(first, second);

const distinctPositions = (values, tolerance) =>
  [...values].sort((first, second) => first - second).reduce((kept, value) => (kept.length && value - kept[kept.length - 1] <= tolerance ? kept : [...kept, value]), []);

const equalSizeGroups = (cards, sizeTolerance) =>
  cards.reduce((groups, card) => {
    const group = groups.find(([first]) => isNear(first.rect.width, card.rect.width, sizeTolerance) && isNear(first.rect.height, card.rect.height, sizeTolerance));
    if (group) group.push(card);
    else groups.push([card]);
    return groups;
  }, []);

const groupArea = (cards) => {
  const left = Math.min(...cards.map((card) => card.rect.left));
  const top = Math.min(...cards.map((card) => card.rect.top));
  const right = Math.max(...cards.map((card) => card.rect.right));
  const bottom = Math.max(...cards.map((card) => card.rect.bottom));
  return (right - left) * (bottom - top);
};

const arrangementOf = (cards, alignmentTolerance) => {
  const rows = distinctPositions(cards.map((card) => card.rect.top), alignmentTolerance).length;
  const columns = distinctPositions(cards.map((card) => card.rect.left), alignmentTolerance).length;
  if (rows === 1) return { arrangement: "row", rows, columns };
  if (columns === 1) return { arrangement: "column", rows, columns };
  return rows * columns === cards.length ? { arrangement: "grid", rows, columns } : null;
};

export function measureComposition(page, threshold, tools) {
  const { minimumShareOfPage, sizeTolerance, alignmentTolerance } = threshold;
  const { rectOf, isCard, shownParts } = boxReader(page, tools);
  const pageArea = areaOf(rectOf(page));
  const cards = shownParts().filter(isCard).map((element) => ({ element, rect: rectOf(element) }));
  const arranged = equalSizeGroups(cards, sizeTolerance)
    .filter((group) => group.length >= 2 && groupArea(group) >= pageArea * minimumShareOfPage)
    .map((group) => ({ group, area: groupArea(group), shape: arrangementOf(group, alignmentTolerance) }))
    .filter(({ shape }) => shape !== null)
    .sort((first, second) => second.area - first.area);
  if (arranged.length === 0) return null;
  const { group, shape } = arranged[0];
  return { ...shape, count: group.length, ...tools.describe(group[0].element) };
}

