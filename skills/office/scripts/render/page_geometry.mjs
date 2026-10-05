import { measureDesignRules } from "./design_rules.mjs";

export function measurePageGeometry(pages, thresholds) {
  const { overlapRatioMinimum, aspectRatioTolerance, imageUpscaleMaximum, textPreviewLength, backgroundShareOfSlide, textContrastMinimum, largeTextContrastMinimum, largeTextShareOfWidth, largeBoldTextShareOfWidth, slideSize, designRules = [] } = thresholds;

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

  const colorIsVisible = (color) => color !== "transparent" && !/(,\s*0\)|\/\s*0%?\))$/.test(color);

  const drawsBorder = (style, side) => parseFloat(style[`border${side}Width`]) > 0 && style[`border${side}Style`] !== "none" && colorIsVisible(style[`border${side}Color`]);

  const paintsFill = (style) => colorIsVisible(style.backgroundColor) || style.backgroundImage !== "none" || style.boxShadow !== "none";

  const paintsBox = (style) => paintsFill(style) || ["Top", "Right", "Bottom", "Left"].some((side) => drawsBorder(style, side));

  const mediaTags = new Set(["IMG", "SVG", "CANVAS", "VIDEO", "PICTURE", "OBJECT", "EMBED", "IFRAME"]);

  const coveringMedia = new Set(["IMG", "CANVAS", "VIDEO", "PICTURE", "OBJECT", "EMBED", "IFRAME"]);

  const intersection = (first, second) => ({
    left: Math.max(first.left, second.left),
    top: Math.max(first.top, second.top),
    right: Math.min(first.right, second.right),
    bottom: Math.min(first.bottom, second.bottom),
  });

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

  return pages.map((page, index) => ({
    index: index + 1,
    width: round(page.getBoundingClientRect().width),
    height: round(page.getBoundingClientRect().height),
    distortedImages: distortedImages(page),
    softImages: softImages(page),
    distortedDrawings: distortedDrawings(page),
    coveredText: coveredText(page),
    lowContrastText: lowContrastText(page),
    designFindings: measureDesignRules(page, designRules, { describe, isMeasurable, elementsOf, ownTextRects, descendantTextRects, unionRect, slideSize }),
  }));
}
