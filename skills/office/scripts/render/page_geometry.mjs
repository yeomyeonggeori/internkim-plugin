import { measureDesignRules } from "./design_rules.mjs";

export const capacityAttribute = "data-kit-capacity";

export function measurePageGeometry(pages, thresholds) {
  const { pixelTolerance, overlapRatioMinimum, aspectRatioTolerance, imageUpscaleMaximum, textPreviewLength, smallestTextShareOfWidth, titleLineMaximum, labelLineMaximum, repeatedFigureMinimum, backgroundShareOfSlide, deadZoneShareOfSlide, markBreadthMinimum, roundSlotMinimum, textContrastMinimum, largeTextContrastMinimum, largeTextShareOfWidth, largeBoldTextShareOfWidth, slideSize, designRules = [] } = thresholds;

  const isMeasurable = (element) => {
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden";
  };

  const describe = (element) => {
    const identifier = element.id ? `#${element.id}` : "";
    const classes = Array.from(element.classList).slice(0, 2).map((name) => `.${name}`).join("");
    const text = (element.textContent || "").replace(/\s+/g, " ").trim().slice(0, textPreviewLength);
    return { selector: `${element.tagName.toLowerCase()}${identifier}${classes}`, text };
  };

  const round = (value) => Math.round(value * 10) / 10;

  const roundRatio = (value) => Math.round(value * 1000) / 1000;

  const elementsOf = (page) => [page, ...Array.from(page.querySelectorAll("*")).filter(isMeasurable)];

  const ownTextRects = (element) =>
    Array.from(element.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
      .flatMap((node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
      });

  const unionRect = (rects) => ({
    left: Math.min(...rects.map((rect) => rect.left)),
    top: Math.min(...rects.map((rect) => rect.top)),
    right: Math.max(...rects.map((rect) => rect.right)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  });

  const area = (rect) => Math.max(0, rect.right - rect.left) * Math.max(0, rect.bottom - rect.top);

  const distortedImages = (page) =>
    Array.from(page.querySelectorAll("img"))
      .filter((image) => isMeasurable(image) && image.naturalWidth > 0 && image.naturalHeight > 0 && getComputedStyle(image).objectFit === "fill")
      .map((image) => {
        const rect = image.getBoundingClientRect();
        return { image, renderedRatio: rect.width / rect.height, naturalRatio: image.naturalWidth / image.naturalHeight };
      })
      .filter(({ renderedRatio, naturalRatio }) => Math.abs(renderedRatio / naturalRatio - 1) > aspectRatioTolerance)
      .map(({ image, renderedRatio, naturalRatio }) => ({ ...describe(image), renderedRatio: roundRatio(renderedRatio), naturalRatio: roundRatio(naturalRatio) }));

  const upscale = (image, rect) => {
    const widthScale = rect.width / image.naturalWidth;
    const heightScale = rect.height / image.naturalHeight;
    return getComputedStyle(image).objectFit === "contain" ? Math.min(widthScale, heightScale) : Math.max(widthScale, heightScale);
  };

  const softImages = (page) =>
    Array.from(page.querySelectorAll("img"))
      .filter((image) => isMeasurable(image) && image.naturalWidth > 0 && image.naturalHeight > 0)
      .map((image) => ({ image, scale: upscale(image, image.getBoundingClientRect()) }))
      .filter(({ scale }) => scale > imageUpscaleMaximum)
      .map(({ image, scale }) => ({ ...describe(image), scale: roundRatio(scale), naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight }));

  const viewBoxRatio = (svg) => {
    const [, , width, height] = (svg.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
    return width > 0 && height > 0 ? width / height : null;
  };

  const keepsProportions = (svg) => (svg.getAttribute("preserveAspectRatio") || "xMidYMid meet").trim() !== "none";

  const distortedDrawings = (page) =>
    Array.from(page.querySelectorAll("svg"))
      .filter((svg) => isMeasurable(svg) && keepsProportions(svg) && viewBoxRatio(svg))
      .map((svg) => {
        const rect = svg.getBoundingClientRect();
        return { svg, renderedRatio: rect.height > 0 ? rect.width / rect.height : 0, naturalRatio: viewBoxRatio(svg) };
      })
      .filter(({ renderedRatio, naturalRatio }) => renderedRatio > 0 && Math.abs(renderedRatio / naturalRatio - 1) > aspectRatioTolerance)
      .map(({ svg, renderedRatio, naturalRatio }) => ({ host: svg.closest("[data-native-chart]") || svg, renderedRatio: roundRatio(renderedRatio), naturalRatio: roundRatio(naturalRatio) }))
      .filter((drawing, index, drawings) => drawings.findIndex((other) => other.host === drawing.host) === index)
      .map(({ host, renderedRatio, naturalRatio }) => ({ ...describe(host), renderedRatio, naturalRatio }));

  const smallText = (page) => {
    const minimum = page.getBoundingClientRect().width * smallestTextShareOfWidth;
    return elementsOf(page)
      .filter((element) => ownTextRects(element).length > 0)
      .map((element) => ({ element, size: parseFloat(getComputedStyle(element).fontSize) }))
      .filter(({ size }) => size > 0 && size < minimum - 0.05)
      .map(({ element, size }) => ({ ...describe(element), fontSize: round(size), minimum: round(minimum) }));
  };

  const colorIsVisible = (color) => color !== "transparent" && !/(,\s*0\)|\/\s*0%?\))$/.test(color);

  const drawsBorder = (style, side) => parseFloat(style[`border${side}Width`]) > 0 && style[`border${side}Style`] !== "none" && colorIsVisible(style[`border${side}Color`]);

  const paintsFill = (style) => colorIsVisible(style.backgroundColor) || style.backgroundImage !== "none" || style.boxShadow !== "none";

  const paintsBox = (style) => paintsFill(style) || ["Top", "Right", "Bottom", "Left"].some((side) => drawsBorder(style, side));

  const enclosesBox = (style) => paintsFill(style) || (drawsBorder(style, "Top") && drawsBorder(style, "Bottom")) || (drawsBorder(style, "Left") && drawsBorder(style, "Right"));

  const mediaTags = new Set(["IMG", "SVG", "CANVAS", "VIDEO", "PICTURE", "OBJECT", "EMBED", "IFRAME"]);

  const coveringMedia = new Set(["IMG", "CANVAS", "VIDEO", "PICTURE", "OBJECT", "EMBED", "IFRAME"]);

  const intersection = (first, second) => ({
    left: Math.max(first.left, second.left),
    top: Math.max(first.top, second.top),
    right: Math.min(first.right, second.right),
    bottom: Math.min(first.bottom, second.bottom),
  });

  const visibleClipOf = (element, page) => {
    let clip = page.getBoundingClientRect();
    for (let ancestor = element.parentElement; ancestor && ancestor !== page; ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      if (style.overflowX !== "visible" || style.overflowY !== "visible") clip = intersection(clip, ancestor.getBoundingClientRect());
    }
    return clip;
  };

  const isBackground = (rect, page) => {
    const frame = page.getBoundingClientRect();
    return area(rect) >= frame.width * frame.height * backgroundShareOfSlide;
  };

  const stackingKey = (element, page, order) => {
    for (let current = element; current && current !== page; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (style.position === "static") continue;
      const zIndex = parseInt(style.zIndex, 10);
      return [Number.isNaN(zIndex) ? 0 : zIndex, 1, order];
    }
    return [0, 0, order];
  };

  const paintsAbove = (first, second) => {
    for (let index = 0; index < first.length; index += 1) {
      if (first[index] !== second[index]) return first[index] > second[index];
    }
    return false;
  };

  const paintedBoxes = (page, elements) =>
    elements
      .map((element, order) => ({ element, order, rect: element.getBoundingClientRect() }))
      .filter(({ element, rect }) => (paintsBox(getComputedStyle(element)) || coveringMedia.has(element.tagName.toUpperCase())) && area(rect) > 0 && !isBackground(rect, page))
      .map((box) => ({ ...box, key: stackingKey(box.element, page, box.order) }));

  const coveredText = (page) => {
    const elements = elementsOf(page).slice(1);
    const boxes = paintedBoxes(page, elements);
    return elements.flatMap((element, order) => {
      const rects = ownTextRects(element);
      if (!rects.length) return [];
      const text = unionRect(rects);
      const key = stackingKey(element, page, order);
      const covers = (box) => !box.element.contains(element) && !element.contains(box.element) && paintsAbove(box.key, key) && area(intersection(text, box.rect)) >= overlapRatioMinimum * area(text);
      const cover = boxes.find(covers);
      return cover ? [{ text: describe(element), box: describe(cover.element), ratio: roundRatio(area(intersection(text, cover.rect)) / area(text)) }] : [];
    });
  };

  const footerOf = (page) => Array.from(page.children).filter((child) => child.tagName === "FOOTER" && isMeasurable(child)).pop();

  const crossesInto = (rect, footerRect) =>
    rect.bottom > footerRect.top + pixelTolerance && rect.top < footerRect.bottom && rect.right > footerRect.left + pixelTolerance && rect.left < footerRect.right - pixelTolerance;

  const footerCrossings = (page) => {
    const footer = footerOf(page);
    if (!footer) return [];
    const footerRect = footer.getBoundingClientRect();
    const top = page.getBoundingClientRect().top;
    return Array.from(page.children)
      .filter((child) => child !== footer && child.tagName !== "ASIDE" && isMeasurable(child))
      .map((child) => ({ child, rect: child.getBoundingClientRect() }))
      .filter(({ rect }) => area(rect) > 0 && !isBackground(rect, page) && crossesInto(rect, footerRect))
      .map(({ child, rect }) => ({ ...describe(child), bottom: round(rect.bottom - top), footerTop: round(footerRect.top - top) }));
  };

  const descendantTextRects = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const rects = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      rects.push(...Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0));
    }
    return rects;
  };

  const lineCount = (rects) => {
    const centers = rects.map((rect) => ({ center: (rect.top + rect.bottom) / 2, height: rect.bottom - rect.top })).sort((first, second) => first.center - second.center);
    let count = 0;
    let lineCenter = -Infinity;
    for (const { center, height } of centers) {
      if (center - lineCenter > height * 0.4) {
        count += 1;
        lineCenter = center;
      }
    }
    return count;
  };

  const longTitles = (page) =>
    Array.from(page.children)
      .filter((child) => ["H1", "H2"].includes(child.tagName) && isMeasurable(child))
      .map((title) => ({ title, lines: lineCount(descendantTextRects(title)) }))
      .filter(({ lines }) => lines > titleLineMaximum)
      .map(({ title, lines }) => ({ ...describe(title), lines, maximum: titleLineMaximum }));

  const longLabels = (page) =>
    Array.from(page.querySelectorAll(".label"))
      .filter(isMeasurable)
      .map((label) => ({ label, lines: lineCount(descendantTextRects(label)) }))
      .filter(({ lines }) => lines > labelLineMaximum)
      .map(({ label, lines }) => ({ ...describe(label), lines, maximum: labelLineMaximum }));

  const figurePattern = /^[+\-−±]?[₩$€£¥]?\d[\d,]*(?:\.\d+)?(?:\s?[^\s\d]{1,4}){0,2}$/;

  const isSeriesPart = (element) => Boolean(element.closest("table, footer, [data-series][data-point]"));

  const isRunningText = (element) => {
    const parent = element.parentElement;
    if (!parent || !getComputedStyle(element).display.startsWith("inline")) return false;
    const parentDisplay = getComputedStyle(parent).display;
    return !parentDisplay.includes("flex") && !parentDisplay.includes("grid") && parent.textContent.trim() !== element.textContent.trim();
  };

  const shownFigures = (page) =>
    elementsOf(page)
      .slice(1)
      .filter((element) => ownTextRects(element).length > 0 && !isSeriesPart(element) && !isRunningText(element))
      .map((element) => ({ element, figure: (element.textContent || "").replace(/\s+/g, " ").trim() }))
      .filter(({ figure }) => figurePattern.test(figure));

  const repeatedFigures = (page) => {
    const shown = new Map();
    shownFigures(page).forEach(({ element, figure }) => shown.set(figure, [...(shown.get(figure) || []), element]));
    return Array.from(shown.entries())
      .filter(([, elements]) => elements.length >= repeatedFigureMinimum)
      .map(([figure, elements]) => ({ figure, count: elements.length, places: elements.map((element) => describe(element.closest("[class]") || element).selector) }));
  };

  const contentRects = (page, elements = elementsOf(page).slice(1)) => {
    const frame = page.getBoundingClientRect();
    const slideArea = frame.width * frame.height;
    return elements.flatMap((element) => {
      const rect = element.getBoundingClientRect();
      const isMedia = mediaTags.has(element.tagName.toUpperCase());
      const isBox = paintsBox(getComputedStyle(element)) && rect.width * rect.height < slideArea * backgroundShareOfSlide;
      const clip = visibleClipOf(element, page);
      if (isMedia || isBox) return [intersection(rect, clip)];
      const style = getComputedStyle(element);
      const textClip = style.overflowX !== "visible" || style.overflowY !== "visible" ? intersection(clip, rect) : clip;
      return ownTextRects(element).map((content) => intersection(content, textClip));
    }).filter((rect) => rect.right > rect.left && rect.bottom > rect.top);
  };

  const mergedBands = (rects, top, bottom) => {
    const intervals = rects
      .map((rect) => [Math.max(rect.top, top) - top, Math.min(rect.bottom, bottom) - top])
      .filter(([start, end]) => end > start)
      .sort((first, second) => first[0] - second[0]);
    const bands = [];
    for (const [start, end] of intervals) {
      const last = bands[bands.length - 1];
      if (last && start <= last[1]) last[1] = Math.max(last[1], end);
      else bands.push([start, end]);
    }
    return bands;
  };

  const contentBands = (page) => {
    const frame = page.getBoundingClientRect();
    return mergedBands(contentRects(page), frame.top, Infinity).map(([top, bottom]) => [round(top), round(bottom)]);
  };

  const uniqueSorted = (values) => Array.from(new Set(values.map(round))).sort((first, second) => first - second);

  const headingSelector = ":scope > :is(h1, h2, .eyebrow, .lead)";

  const unionOf = (rects) => ({
    left: Math.min(...rects.map((rect) => rect.left)),
    top: Math.min(...rects.map((rect) => rect.top)),
    right: Math.max(...rects.map((rect) => rect.right)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  });

  const headingsOf = (page) => Array.from(page.querySelectorAll(headingSelector)).filter(isMeasurable);

  const bodyElements = (page) => {
    const outside = [...headingsOf(page), footerOf(page)].filter(Boolean);
    return elementsOf(page).slice(1).filter((element) => !outside.some((part) => part.contains(element)));
  };

  const headingSides = (page) => {
    const headings = headingsOf(page);
    if (!headings.length) return {};
    const bodyRects = contentRects(page, bodyElements(page));
    if (!bodyRects.length) return {};
    const heading = unionOf(headings.map((element) => element.getBoundingClientRect()));
    const body = unionOf(bodyRects);
    if (body.top >= heading.bottom - pixelTolerance) return { top: heading.bottom };
    if (body.left >= heading.right - pixelTolerance) return { top: body.top, left: body.left };
    if (body.right <= heading.left + pixelTolerance) return { top: body.top, right: body.right };
    return {};
  };

  const bodyFrame = (page, rects) => {
    const footer = footerOf(page);
    const box = page.getBoundingClientRect();
    const style = getComputedStyle(page);
    const sides = headingSides(page);
    return {
      left: sides.left ?? box.left + (parseFloat(style.paddingLeft) || 0),
      right: sides.right ?? box.right - (parseFloat(style.paddingRight) || 0),
      top: sides.top ?? Math.min(...rects.map((rect) => rect.top)),
      bottom: footer ? footer.getBoundingClientRect().top : Math.max(...rects.map((rect) => rect.bottom)),
    };
  };

  const largestEmptyRectangle = (frame, rects) => {
    const inside = rects.map((rect) => intersection(rect, frame)).filter((rect) => rect.right > rect.left && rect.bottom > rect.top);
    const xs = uniqueSorted([frame.left, frame.right, ...inside.flatMap((rect) => [rect.left, rect.right])]);
    const ys = uniqueSorted([frame.top, frame.bottom, ...inside.flatMap((rect) => [rect.top, rect.bottom])]);
    const columns = xs.length - 1;
    const isEmpty = (row, column) => {
      const x = (xs[column] + xs[column + 1]) / 2;
      const y = (ys[row] + ys[row + 1]) / 2;
      return !inside.some((rect) => rect.left <= x && x <= rect.right && rect.top <= y && y <= rect.bottom);
    };
    const heights = new Array(columns).fill(0);
    let best = null;
    for (let row = 0; row < ys.length - 1; row += 1) {
      for (let column = 0; column < columns; column += 1) heights[column] = isEmpty(row, column) ? heights[column] + ys[row + 1] - ys[row] : 0;
      const stack = [];
      for (let column = 0; column <= columns; column += 1) {
        const height = column < columns ? heights[column] : 0;
        while (stack.length && heights[stack[stack.length - 1]] >= height) {
          const tallest = heights[stack.pop()];
          const left = stack.length ? xs[stack[stack.length - 1] + 1] : xs[0];
          const area = tallest * (xs[column] - left);
          if (tallest > 0 && (!best || area > best.area)) best = { area, left, right: xs[column], top: ys[row + 1] - tallest, bottom: ys[row + 1] };
        }
        stack.push(column);
      }
    }
    return best;
  };

  const slackEvenness = 0.2;
  const slackPasses = 4;

  const isEven = (one, other) => Math.abs(one - other) <= slackEvenness * Math.max(one, other) + pixelTolerance;
  const touches = (edge, side) => Math.abs(edge - side) <= pixelTolerance;
  const overlapsAcross = (rect, start, end, [low, high]) => rect[low] < end - pixelTolerance && rect[high] > start + pixelTolerance;

  const mirroredSlack = (region, frame, parts) => {
    for (const [low, high, crossLow, crossHigh] of [["left", "right", "top", "bottom"], ["top", "bottom", "left", "right"]]) {
      const atLow = touches(region[low], frame[low]);
      const atHigh = touches(region[high], frame[high]);
      if (atLow === atHigh) continue;
      const beside = parts.filter((rect) => overlapsAcross(rect, region[crossLow], region[crossHigh], [crossLow, crossHigh]));
      if (!beside.length) continue;
      const slack = region[high] - region[low];
      const reach = atLow ? Math.max(...beside.map((rect) => rect[high])) : Math.min(...beside.map((rect) => rect[low]));
      const opposite = atLow ? frame[high] - reach : reach - frame[low];
      if (!isEven(slack, opposite)) continue;
      return { [crossLow]: region[crossLow], [crossHigh]: region[crossHigh], [low]: atLow ? reach : frame[low], [high]: atLow ? frame[high] : reach };
    }
    return null;
  };

  const unbalancedEmptyRectangle = (frame, parts) => {
    const inside = parts.map((rect) => intersection(rect, frame)).filter((rect) => rect.right > rect.left && rect.bottom > rect.top);
    let filled = inside;
    for (let pass = 0; pass < slackPasses; pass += 1) {
      const region = largestEmptyRectangle(frame, filled);
      if (!region) return null;
      const mirror = mirroredSlack(region, frame, inside);
      if (!mirror) return region;
      filled = [...filled, region, mirror];
    }
    return null;
  };

  const figureRects = (page) => Array.from(page.querySelectorAll("figure")).filter(isMeasurable).map((figure) => figure.getBoundingClientRect());

  const uncaptionedRects = (page) => contentRects(page, bodyElements(page).filter((element) => !element.closest("figcaption")));

  const drawnFigureRects = (page) =>
    Array.from(page.querySelectorAll("figure"))
      .filter(isMeasurable)
      .flatMap((figure) => Array.from(figure.children).filter((child) => child.tagName !== "FIGCAPTION" && isMeasurable(child)))
      .map((child) => child.getBoundingClientRect());

  const contentFrame = (frame, rects) => {
    const inside = rects.map((rect) => intersection(rect, frame)).filter((rect) => rect.right > rect.left && rect.bottom > rect.top);
    if (!inside.length) return null;
    return { left: frame.left, right: frame.right, top: Math.min(...inside.map((rect) => rect.top)), bottom: Math.max(...inside.map((rect) => rect.bottom)) };
  };

  const emptyRegion = (page) => {
    const rects = contentRects(page);
    if (!rects.length) return null;
    const body = bodyFrame(page, rects);
    if (body.bottom <= body.top || body.right <= body.left) return null;
    const parts = [...rects, ...figureRects(page)];
    const frame = contentFrame(body, [...uncaptionedRects(page), ...drawnFigureRects(page)]);
    if (!frame || frame.bottom <= frame.top) return null;
    const region = unbalancedEmptyRectangle(frame, parts);
    if (!region) return null;
    const origin = page.getBoundingClientRect();
    const relative = (rect) => ({ left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) });
    const share = roundRatio(region.area / ((frame.right - frame.left) * (frame.bottom - frame.top)));
    return { ...relative(region), frame: relative(frame), share };
  };

  const contentBoxOf = (box, rect) => {
    const style = getComputedStyle(box);
    const inset = (side) => (parseFloat(style[`border${side}Width`]) || 0) + (parseFloat(style[`padding${side}`]) || 0);
    return { top: rect.top + inset("Top"), bottom: rect.bottom - inset("Bottom") };
  };

  const emptyHeightInside = (box, rect, page) => {
    const inner = [...ownTextRects(box), ...contentRects(page, Array.from(box.querySelectorAll("*")).filter(isMeasurable))];
    const { top, bottom } = contentBoxOf(box, rect);
    const covered = mergedBands(inner, top, bottom).reduce((sum, [start, end]) => sum + end - start, 0);
    return Math.max(0, bottom - top - covered);
  };

  const rowsOf = (boxes) => {
    const rows = new Map();
    for (const box of boxes) {
      const key = `${Math.round(box.rect.top)}:${Math.round(box.rect.bottom)}`;
      const siblings = rows.get(box.element.parentElement) || new Map();
      siblings.set(key, [...(siblings.get(key) || []), box]);
      rows.set(box.element.parentElement, siblings);
    }
    return Array.from(rows.values()).flatMap((siblings) => Array.from(siblings.values()));
  };

  const hollowBoxes = (page) => {
    const frame = page.getBoundingClientRect();
    const boxes = elementsOf(page)
      .slice(1)
      .filter((element) => !mediaTags.has(element.tagName.toUpperCase()) && enclosesBox(getComputedStyle(element)) && descendantTextRects(element).length > 0)
      .map((element) => ({ element, rect: element.getBoundingClientRect() }))
      .filter(({ rect }) => area(rect) > 0 && !isBackground(rect, page))
      .map(({ element, rect }) => ({ element, rect, empty: emptyHeightInside(element, rect, page) }));
    return rowsOf(boxes)
      .filter((row) => Math.min(...row.map((box) => box.empty)) >= frame.height * deadZoneShareOfSlide)
      .flat()
      .map(({ element, rect, empty }) => ({ ...describe(element), height: round(rect.bottom - rect.top), emptyHeight: round(empty) }));
  };

  const coveredLength = (intervals) => {
    let covered = 0;
    let reach = -Infinity;
    intervals.sort((first, second) => first[0] - second[0]).forEach(([start, end]) => {
      covered += Math.max(0, end - Math.max(start, reach));
      reach = Math.max(reach, end);
    });
    return covered;
  };

  const barBreadth = (chart) => {
    const plot = chart.querySelector(".kit-plot-area, .kit-bar-area");
    const bars = Array.from(chart.querySelectorAll(".kit-bar, .kit-segment")).filter(isMeasurable).map((bar) => bar.getBoundingClientRect());
    if (!plot || !bars.length) return null;
    const area = plot.getBoundingClientRect();
    const isHorizontal = Boolean(chart.querySelector(".kit-bar.kit-horizontal"));
    const along = isHorizontal ? ["top", "bottom"] : ["left", "right"];
    const breadth = area[along[1]] - area[along[0]];
    if (breadth <= 0) return null;
    return { kind: "bars", share: roundRatio(coveredLength(bars.map((bar) => [bar[along[0]], bar[along[1]]])) / breadth), minimum: markBreadthMinimum };
  };

  const ringSlot = (chart, ring) => {
    const figure = chart.closest("figure") || chart;
    const box = figure.getBoundingClientRect();
    const caption = Array.from(figure.children).find((child) => child.tagName === "FIGCAPTION" && isMeasurable(child));
    const legend = chart.querySelector(".kit-donut-legend");
    const ringBox = ring.getBoundingClientRect();
    const legendBox = legend && isMeasurable(legend) ? legend.getBoundingClientRect() : null;
    const besideLegend = legendBox && legendBox.top < ringBox.bottom && legendBox.bottom > ringBox.top ? legendBox.right - legendBox.left + Math.max(0, legendBox.left - ringBox.right) : 0;
    const captionHeight = caption ? caption.getBoundingClientRect().bottom - Math.min(caption.getBoundingClientRect().top, ringBox.bottom) : 0;
    return { width: box.width - besideLegend, height: box.height - captionHeight };
  };

  const ringFill = (chart) => {
    const ring = chart.querySelector(".kit-donut-ring");
    if (!ring || !isMeasurable(ring)) return null;
    const box = ring.getBoundingClientRect();
    const slot = ringSlot(chart, ring);
    const largest = Math.max(slot.width, slot.height);
    if (largest <= 0) return null;
    return { kind: "round", share: roundRatio(Math.min(box.width, box.height) / largest), minimum: roundSlotMinimum };
  };

  const underfilledCharts = (page) =>
    Array.from(page.querySelectorAll("[data-native-chart]"))
      .filter(isMeasurable)
      .map((chart) => ({ chart, fill: ringFill(chart) || barBreadth(chart) }))
      .filter(({ fill }) => fill && fill.share < fill.minimum)
      .map(({ chart, fill }) => ({ ...describe(chart.closest("figure") || chart), ...fill }));

  const colorChannels = (color) => {
    const match = /^rgba?\(([^)]+)\)$/.exec(String(color).trim());
    if (!match) return null;
    const [red, green, blue, alpha = 1] = match[1].split(",").map((part) => parseFloat(part));
    return { red, green, blue, alpha };
  };

  const blend = (top, bottom) => ({
    red: top.red * top.alpha + bottom.red * (1 - top.alpha),
    green: top.green * top.alpha + bottom.green * (1 - top.alpha),
    blue: top.blue * top.alpha + bottom.blue * (1 - top.alpha),
    alpha: 1,
  });

  const linearChannel = (channel) => {
    const share = channel / 255;
    return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
  };

  const luminance = ({ red, green, blue }) => 0.2126 * linearChannel(red) + 0.7152 * linearChannel(green) + 0.0722 * linearChannel(blue);

  const contrastRatio = (first, second) => {
    const [lighter, darker] = [luminance(first), luminance(second)].sort((one, other) => other - one);
    return (lighter + 0.05) / (darker + 0.05);
  };

  const paintOrder = (page) => {
    const elements = elementsOf(page);
    return new Map(elements.map((element, order) => [element, stackingKey(element, page, order)]));
  };

  const isMedia = (element) => mediaTags.has(element.tagName.toUpperCase());

  const fillsUnder = (page, element, order) => {
    const text = unionRect(ownTextRects(element));
    const center = { x: (text.left + text.right) / 2, y: (text.top + text.bottom) / 2 };
    const key = order.get(element);
    return elementsOf(page)
      .filter((candidate) => !element.contains(candidate) || candidate === element)
      .filter((candidate) => candidate === page || candidate.contains(element) || paintsAbove(key, order.get(candidate)))
      .filter((candidate) => {
        const style = getComputedStyle(candidate);
        return isMedia(candidate) || colorIsVisible(style.backgroundColor) || style.backgroundImage !== "none";
      })
      .filter((candidate) => {
        const rect = candidate.getBoundingClientRect();
        return rect.left <= center.x && center.x <= rect.right && rect.top <= center.y && center.y <= rect.bottom;
      })
      .sort((first, second) => (paintsAbove(order.get(first), order.get(second)) ? 1 : paintsAbove(order.get(second), order.get(first)) ? -1 : 0));
  };

  const backdropOf = (page, element, order) => {
    let backdrop = null;
    for (const fill of fillsUnder(page, element, order)) {
      const style = getComputedStyle(fill);
      if (isMedia(fill) || style.backgroundImage.includes("url(")) return null;
      const color = colorChannels(style.backgroundColor);
      if (!color || color.alpha === 0) continue;
      backdrop = backdrop ? blend(color, backdrop) : color.alpha >= 1 ? color : null;
    }
    return backdrop;
  };

  const opacityOf = (element) => {
    let opacity = 1;
    for (let current = element; current; current = current.parentElement) {
      const own = parseFloat(getComputedStyle(current).opacity);
      opacity *= Number.isNaN(own) ? 1 : own;
    }
    return opacity;
  };

  const isLargeText = (style, slideWidth) => {
    const size = parseFloat(style.fontSize);
    return size >= slideWidth * largeTextShareOfWidth || (parseInt(style.fontWeight, 10) >= 700 && size >= slideWidth * largeBoldTextShareOfWidth);
  };

  const lowContrastText = (page) => {
    const slideWidth = page.getBoundingClientRect().width;
    const order = paintOrder(page);
    return elementsOf(page)
      .filter((element) => ownTextRects(element).length > 0)
      .flatMap((element) => {
        const style = getComputedStyle(element);
        const ink = colorChannels(style.color);
        const backdrop = backdropOf(page, element, order);
        if (!ink || !backdrop) return [];
        const ratio = contrastRatio(blend({ ...ink, alpha: ink.alpha * opacityOf(element) }, backdrop), backdrop);
        const minimum = isLargeText(style, slideWidth) ? largeTextContrastMinimum : textContrastMinimum;
        if (ratio >= minimum) return [];
        return [{ ...describe(element), ratio: Math.round(ratio * 100) / 100, minimum }];
      });
  };

  const titleStyle = (page) => {
    const title = Array.from(page.children).find((child) => ["H1", "H2"].includes(child.tagName) && isMeasurable(child));
    if (!title) return null;
    const style = getComputedStyle(title);
    const lines = descendantTextRects(title);
    return {
      ...describe(title),
      fontFamily: style.fontFamily,
      fontWeight: parseInt(style.fontWeight, 10),
      color: style.color,
      textAlign: style.textAlign,
      textLeft: lines.length ? round(Math.min(...lines.map((rect) => rect.left)) - page.getBoundingClientRect().left) : null,
    };
  };

  const near = (first, second) => Math.abs(first - second) <= pixelTolerance;

  const sharesTopOrMiddle = (first, second) => near(first.top, second.top) || near(first.top + first.bottom, second.top + second.bottom);

  const sharesAColumnEdge = (first, second) => near(first.left, second.left) || near(first.right, second.right) || near(first.left + first.right, second.left + second.right);

  const isPlacedByHand = (element) => ["absolute", "fixed"].includes(getComputedStyle(element).position);

  const emphasisClasses = new Set(["pick", "done", "up", "down"]);

  const kindOf = (element) => Array.from(element.classList).filter((name) => !emphasisClasses.has(name)).sort().join(".");

  const siblingGroups = (parent) => {
    const groups = new Map();
    Array.from(parent.children)
      .filter((child) => isMeasurable(child) && !isPlacedByHand(child) && !getComputedStyle(child).display.startsWith("inline") && kindOf(child) && descendantTextRects(child).length > 0)
      .forEach((child) => {
        const key = `${child.tagName}.${kindOf(child)}`;
        groups.set(key, [...(groups.get(key) || []), { element: child, rect: child.getBoundingClientRect() }]);
      });
    return Array.from(groups.values()).filter((group) => group.length >= 2);
  };

  const pairMisalignment = (first, second) => {
    const [one, other] = [first.rect, second.rect];
    const sideBySide = one.top < other.bottom && other.top < one.bottom;
    const stacked = one.left < other.right && other.left < one.right;
    if (sideBySide && !stacked && !sharesTopOrMiddle(one, other)) return { axis: "row", offset: round(Math.abs(one.top - other.top)) };
    if (stacked && !sideBySide && !sharesAColumnEdge(one, other)) return { axis: "column", offset: round(Math.abs(one.left - other.left)) };
    return null;
  };

  const unevenGap = (group, low, high) => {
    const ordered = [...group].sort((one, other) => one.rect[low] - other.rect[low]);
    const gaps = ordered.slice(1).map((box, index) => ({ first: ordered[index], second: box, gap: box.rect[low] - ordered[index].rect[high] }));
    if (gaps.length < 2) return null;
    const widest = gaps.reduce((one, other) => (other.gap > one.gap ? other : one));
    const narrowest = Math.min(...gaps.map(({ gap }) => gap));
    return widest.gap - narrowest > pixelTolerance ? { first: widest.first, second: widest.second, offset: round(widest.gap - narrowest) } : null;
  };

  const unevenSpacing = (group) => {
    const pairs = group.flatMap((first, index) => group.slice(index + 1).map((second) => [first.rect, second.rect]));
    const isColumn = pairs.every(([one, other]) => one.left < other.right && other.left < one.right && !(one.top < other.bottom && other.top < one.bottom));
    const isRow = pairs.every(([one, other]) => one.top < other.bottom && other.top < one.bottom && !(one.left < other.right && other.left < one.right));
    const uneven = isColumn ? unevenGap(group, "top", "bottom") : isRow ? unevenGap(group, "left", "right") : null;
    return uneven ? [{ first: uneven.first, second: uneven.second, misalignment: { axis: isColumn ? "column spacing" : "row spacing", offset: uneven.offset } }] : [];
  };

  const misalignedSiblings = (page) =>
    elementsOf(page)
      .flatMap(siblingGroups)
      .flatMap((group) => [...group.flatMap((first, index) => group.slice(index + 1).map((second) => ({ first, second, misalignment: pairMisalignment(first, second) }))), ...unevenSpacing(group)])
      .filter(({ misalignment }) => misalignment)
      .map(({ first, second, misalignment }) => ({ first: describe(first.element), second: describe(second.element), ...misalignment }));

  return pages.map((page, index) => ({
    index: index + 1,
    width: round(page.getBoundingClientRect().width),
    height: round(page.getBoundingClientRect().height),
    contentBands: contentBands(page),
    emptyRegion: emptyRegion(page),
    hollowBoxes: hollowBoxes(page),
    distortedImages: distortedImages(page),
    softImages: softImages(page),
    distortedDrawings: distortedDrawings(page),
    smallText: smallText(page),
    coveredText: coveredText(page),
    footerCrossings: footerCrossings(page),
    longTitles: longTitles(page),
    longLabels: longLabels(page),
    repeatedFigures: repeatedFigures(page),
    underfilledCharts: underfilledCharts(page),
    lowContrastText: lowContrastText(page),
    misalignedSiblings: misalignedSiblings(page),
    titleStyle: titleStyle(page),
    capacity: JSON.parse(page.getAttribute(capacityAttribute) || "[]"),
    designFindings: measureDesignRules(page, designRules, { describe, isMeasurable, elementsOf, ownTextRects, descendantTextRects, unionRect, slideSize }),
  }));
}
