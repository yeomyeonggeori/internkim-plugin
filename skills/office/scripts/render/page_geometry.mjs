export const capacityAttribute = "data-kit-capacity";

export function measurePageGeometry(pages, thresholds) {
  const { pixelTolerance, overlapRatioMinimum, aspectRatioTolerance, textPreviewLength, smallestTextShareOfWidth, titleLineMaximum, labelLineMaximum, backgroundShareOfSlide, deadZoneShareOfSlide } = thresholds;

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

  const describeRect = (rect) => ({ left: round(rect.left), top: round(rect.top), right: round(rect.right), bottom: round(rect.bottom) });

  const elementsOf = (page) => [page, ...Array.from(page.querySelectorAll("*")).filter(isMeasurable)];

  const overflowingElements = (page) => {
    const overflowing = elementsOf(page).filter((element) => {
      if (element.clientWidth === 0 || element.clientHeight === 0) return false;
      return element.scrollHeight > element.clientHeight + pixelTolerance || element.scrollWidth > element.clientWidth + pixelTolerance;
    });
    return overflowing.filter((element) => !overflowing.some((other) => other !== element && element.contains(other)));
  };

  const describeOverflow = (element) => ({
    ...describe(element),
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  });

  const isOutsideFrame = (rect, frame) =>
    rect.width > 0 && rect.height > 0 &&
    (rect.left < frame.left - pixelTolerance || rect.top < frame.top - pixelTolerance ||
      rect.right > frame.right + pixelTolerance || rect.bottom > frame.bottom + pixelTolerance);

  const elementsOutsideFrame = (page) => {
    const frame = page.getBoundingClientRect();
    const isOutside = (element) => isOutsideFrame(element.getBoundingClientRect(), frame);
    return elementsOf(page)
      .slice(1)
      .filter((element) => isOutside(element) && !(element.parentElement !== page && isOutside(element.parentElement)));
  };

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

  const overlapRatio = (first, second) => {
    const shared = area({
      left: Math.max(first.left, second.left),
      top: Math.max(first.top, second.top),
      right: Math.min(first.right, second.right),
      bottom: Math.min(first.bottom, second.bottom),
    });
    return shared / Math.min(area(first), area(second));
  };

  const overlappingText = (page) => {
    const boxes = elementsOf(page)
      .map((element) => ({ element, rects: ownTextRects(element) }))
      .filter((box) => box.rects.length > 0)
      .map((box) => ({ element: box.element, rect: unionRect(box.rects) }));
    const overlaps = [];
    boxes.forEach((first, index) => {
      boxes.slice(index + 1).forEach((second) => {
        if (first.element.contains(second.element) || second.element.contains(first.element)) return;
        const ratio = overlapRatio(first.rect, second.rect);
        if (ratio >= overlapRatioMinimum) {
          overlaps.push({ first: describe(first.element), second: describe(second.element), ratio: roundRatio(ratio) });
        }
      });
    });
    return overlaps;
  };

  const distortedImages = (page) =>
    Array.from(page.querySelectorAll("img"))
      .filter((image) => isMeasurable(image) && image.naturalWidth > 0 && image.naturalHeight > 0 && getComputedStyle(image).objectFit === "fill")
      .map((image) => {
        const rect = image.getBoundingClientRect();
        return { image, renderedRatio: rect.width / rect.height, naturalRatio: image.naturalWidth / image.naturalHeight };
      })
      .filter(({ renderedRatio, naturalRatio }) => Math.abs(renderedRatio / naturalRatio - 1) > aspectRatioTolerance)
      .map(({ image, renderedRatio, naturalRatio }) => ({ ...describe(image), renderedRatio: roundRatio(renderedRatio), naturalRatio: roundRatio(naturalRatio) }));

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

  const bodyFrame = (page, rects) => {
    const footer = footerOf(page);
    const top = Math.min(...rects.map((rect) => rect.top));
    const bottom = footer ? footer.getBoundingClientRect().top : Math.max(...rects.map((rect) => rect.bottom));
    const box = page.getBoundingClientRect();
    const style = getComputedStyle(page);
    return { left: box.left + (parseFloat(style.paddingLeft) || 0), right: box.right - (parseFloat(style.paddingRight) || 0), top, bottom };
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

  const figureRects = (page) => Array.from(page.querySelectorAll("figure")).filter(isMeasurable).map((figure) => figure.getBoundingClientRect());

  const emptyRegion = (page) => {
    const rects = contentRects(page);
    if (!rects.length) return null;
    const frame = bodyFrame(page, rects);
    if (frame.bottom <= frame.top || frame.right <= frame.left) return null;
    const region = largestEmptyRectangle(frame, [...rects, ...figureRects(page)]);
    if (!region) return null;
    const origin = page.getBoundingClientRect();
    const relative = (rect) => ({ left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) });
    return { ...relative(region), frame: relative(frame) };
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

  return pages.map((page, index) => ({
    index: index + 1,
    width: round(page.getBoundingClientRect().width),
    height: round(page.getBoundingClientRect().height),
    contentBands: contentBands(page),
    emptyRegion: emptyRegion(page),
    hollowBoxes: hollowBoxes(page),
    overflow: overflowingElements(page).map(describeOverflow),
    outOfFrame: elementsOutsideFrame(page).map((element) => ({ ...describe(element), rect: describeRect(element.getBoundingClientRect()) })),
    overlaps: overlappingText(page),
    distortedImages: distortedImages(page),
    smallText: smallText(page),
    coveredText: coveredText(page),
    footerCrossings: footerCrossings(page),
    longTitles: longTitles(page),
    longLabels: longLabels(page),
    capacity: JSON.parse(page.getAttribute(capacityAttribute) || "[]"),
  }));
}
