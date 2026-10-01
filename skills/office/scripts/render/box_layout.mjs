export const exportedShapeAttribute = "data-internkim-pptx-shape";
export const exportedBeforeShapeAttribute = "data-internkim-pptx-shape-before";
export const exportedAfterShapeAttribute = "data-internkim-pptx-shape-after";

export function extractBoxLayout({ exportedShapeAttribute, exportedBeforeShapeAttribute, exportedAfterShapeAttribute, nativeTableAttribute, pages }) {
  const replacedTags = new Set(["IMG", "SVG", "CANVAS", "VIDEO", "IFRAME", "OBJECT", "EMBED", "PICTURE", "INPUT", "BUTTON", "SELECT", "TEXTAREA", "MATH", "AUDIO"]);
  const skippedTags = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "HEAD", "META", "LINK", "TITLE"]);
  const pseudoAttributes = { "::before": exportedBeforeShapeAttribute, "::after": exportedAfterShapeAttribute };
  const round = (value) => Math.round(value * 100) / 100;
  const pixels = (value) => parseFloat(value) || 0;

  const colorAlpha = (color) => {
    if (!color || color === "transparent") return 0;
    const slash = color.match(/\/\s*([\d.]+)(%?)\s*\)$/);
    if (slash) return slash[2] ? parseFloat(slash[1]) / 100 : parseFloat(slash[1]);
    const legacy = color.match(/^rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\s*\)$/);
    return legacy ? parseFloat(legacy[1]) : 1;
  };

  const hasOnlyTranslation = (transform) => {
    if (!transform || transform === "none") return true;
    const values = transform.match(/-?[\d.e]+/g)?.map(Number) || [];
    return transform.startsWith("matrix(") && values[0] === 1 && values[1] === 0 && values[2] === 0 && values[3] === 1;
  };

  const drawsAsPicture = (element, style) =>
    replacedTags.has(element.tagName.toUpperCase()) ||
    element instanceof SVGElement ||
    !hasOnlyTranslation(style.transform) ||
    style.filter !== "none" ||
    style.backdropFilter && style.backdropFilter !== "none" ||
    style.mixBlendMode !== "normal" ||
    style.clipPath !== "none" ||
    (style.maskImage || style.webkitMaskImage || "none") !== "none" ||
    style.perspective !== "none" ||
    style.writingMode !== "horizontal-tb" ||
    (style.webkitBackgroundClip || style.backgroundClip) === "text";

  const isSkipped = (element) => skippedTags.has(element.tagName.toUpperCase()) || element.classList.contains("notes");

  const pseudoPaints = (style) => style.content !== "none" && style.content !== "normal" && style.display !== "none";

  const childItems = (element) => {
    const items = [];
    const before = getComputedStyle(element, "::before");
    if (pseudoPaints(before)) items.push({ element, pseudo: "::before", style: before });
    for (const child of element.children) {
      if (isSkipped(child)) continue;
      const style = getComputedStyle(child);
      if (style.display === "none") continue;
      items.push({ element: child, pseudo: "", style });
    }
    const after = getComputedStyle(element, "::after");
    if (pseudoPaints(after)) items.push({ element, pseudo: "::after", style: after });
    return items;
  };

  const parentDisplayOf = (item) => {
    const parent = item.pseudo ? item.element : item.element.parentElement;
    return parent ? getComputedStyle(parent).display : "block";
  };

  const createsStackingContext = (style) =>
    parseFloat(style.opacity) < 1 || style.transform !== "none" || style.filter !== "none" || style.isolation === "isolate" || style.mixBlendMode !== "normal" || style.clipPath !== "none";

  const layerOf = (item) => {
    const style = item.style;
    const zIndex = style.zIndex === "auto" ? null : parseInt(style.zIndex, 10);
    if (style.position !== "static") return zIndex ?? 0;
    if (zIndex !== null && /(flex|grid)$/.test(parentDisplayOf(item))) return zIndex;
    if (createsStackingContext(style)) return 0;
    return null;
  };

  const paintOrder = (root) => {
    const negative = [];
    const flow = [];
    const layered = [];
    const positive = [];
    const collect = (element) => {
      for (const child of childItems(element)) {
        const layer = layerOf(child);
        if (layer === null) {
          flow.push(child);
          if (!child.pseudo) collect(child.element);
        } else if (layer < 0) negative.push({ child, layer });
        else if (layer > 0) positive.push({ child, layer });
        else layered.push({ child, layer });
      }
    };
    if (!root.pseudo) collect(root.element);
    const byLayer = (first, second) => first.layer - second.layer;
    const painted = ({ child }) => paintOrder(child);
    return [root, ...negative.sort(byLayer).flatMap(painted), ...flow, ...layered.flatMap(painted), ...positive.sort(byLayer).flatMap(painted)];
  };

  const containingBlockOf = (element) => {
    for (let current = element; current; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (style.position !== "static" || style.transform !== "none") {
        const rect = current.getBoundingClientRect();
        return { left: rect.left + pixels(style.borderLeftWidth), top: rect.top + pixels(style.borderTopWidth), right: rect.right - pixels(style.borderRightWidth), bottom: rect.bottom - pixels(style.borderBottomWidth) };
      }
    }
    return { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight };
  };

  const outerSize = (style, axis) => {
    const [size, first, second] = axis === "x" ? ["width", "Left", "Right"] : ["height", "Top", "Bottom"];
    const value = pixels(style[size]);
    if (style.boxSizing === "border-box") return value;
    return value + pixels(style[`padding${first}`]) + pixels(style[`padding${second}`]) + pixels(style[`border${first}Width`]) + pixels(style[`border${second}Width`]);
  };

  const pseudoAxes = {
    x: { start: "left", end: "right", size: "width", marginStart: "marginLeft", marginEnd: "marginRight" },
    y: { start: "top", end: "bottom", size: "height", marginStart: "marginTop", marginEnd: "marginBottom" },
  };

  const pseudoSpan = (style, block, axis) => {
    const { start, end, size, marginStart, marginEnd } = pseudoAxes[axis];
    if (![style[start], style[end]].every((value) => value === "auto" || value.endsWith("px"))) return null;
    const hasStart = style[start] !== "auto";
    const hasEnd = style[end] !== "auto";
    if (!hasStart && !hasEnd) return null;
    const margins = pixels(style[marginStart]) + pixels(style[marginEnd]);
    const stretched = hasStart && hasEnd ? block[end] - block[start] - pixels(style[start]) - pixels(style[end]) - margins : null;
    const extent = style[size].endsWith("px") ? outerSize(style, axis) : stretched;
    if (extent === null) return null;
    const from = hasStart ? block[start] + pixels(style[start]) + pixels(style[marginStart]) : block[end] - pixels(style[end]) - pixels(style[marginEnd]) - extent;
    return [from, from + extent];
  };

  const absolutePseudoRect = (item) => {
    const block = containingBlockOf(item.element);
    const horizontal = pseudoSpan(item.style, block, "x");
    const vertical = pseudoSpan(item.style, block, "y");
    if (!horizontal || !vertical) return null;
    return { left: horizontal[0], top: vertical[0], right: horizontal[1], bottom: vertical[1] };
  };

  const rectOf = (item) => {
    if (item.pseudo) {
      const positioned = item.style.position === "absolute" ? absolutePseudoRect(item) : null;
      if (positioned) return { rect: positioned, exact: true };
      const host = item.element.getBoundingClientRect();
      return { rect: { left: host.left, top: host.top, right: host.right, bottom: host.bottom }, exact: false };
    }
    const rects = Array.from(item.element.getClientRects()).filter((rect) => rect.width > 0 || rect.height > 0);
    const whole = item.element.getBoundingClientRect();
    return { rect: { left: whole.left, top: whole.top, right: whole.right, bottom: whole.bottom }, exact: rects.length === 1 };
  };

  const opacityOf = (item, section) => {
    let opacity = item.pseudo ? parseFloat(item.style.opacity) : 1;
    for (let element = item.element; element; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (style.visibility !== "visible" && element === item.element && !item.pseudo) return 0;
      opacity *= parseFloat(style.opacity);
      if (element === section) break;
    }
    return opacity;
  };

  const isInsidePicture = (item, section) => {
    if (item.pseudo && drawsAsPicture(item.element, item.style)) return true;
    for (let element = item.element; element && element !== section; element = element.parentElement) {
      if (drawsAsPicture(element, getComputedStyle(element))) return true;
    }
    return false;
  };

  const isClippedByAncestor = (item, rect, section) => {
    const start = item.pseudo ? item.element : item.element.parentElement;
    for (let element = start; element && element !== section; element = element.parentElement) {
      const style = getComputedStyle(element);
      if (style.overflowX === "visible" && style.overflowY === "visible") continue;
      const clip = element.getBoundingClientRect();
      if (rect.left < clip.left - 0.5 || rect.top < clip.top - 0.5 || rect.right > clip.right + 0.5 || rect.bottom > clip.bottom + 0.5) return true;
    }
    return false;
  };

  const sidesOf = (style) =>
    ["Top", "Right", "Bottom", "Left"].map((side) => {
      const width = pixels(style[`border${side}Width`]);
      const color = style[`border${side}Color`];
      const lineStyle = style[`border${side}Style`];
      return { width, color, lineStyle, visible: width > 0 && lineStyle !== "none" && lineStyle !== "hidden" && colorAlpha(color) > 0 };
    });

  const cornerRadii = (style, width, height) => {
    const corners = ["TopLeft", "TopRight", "BottomRight", "BottomLeft"].map((corner) => {
      const parts = style[`border${corner}Radius`].split(" ");
      const horizontal = parts[0].endsWith("%") ? (parseFloat(parts[0]) / 100) * width : pixels(parts[0]);
      const vertical = (parts[1] || parts[0]).endsWith("%") ? (parseFloat(parts[1] || parts[0]) / 100) * height : pixels(parts[1] || parts[0]);
      return { horizontal, vertical };
    });
    const [topLeft, topRight, bottomRight, bottomLeft] = corners;
    const factor = Math.min(
      1,
      width / Math.max(topLeft.horizontal + topRight.horizontal, 1e-9),
      width / Math.max(bottomLeft.horizontal + bottomRight.horizontal, 1e-9),
      height / Math.max(topLeft.vertical + bottomLeft.vertical, 1e-9),
      height / Math.max(topRight.vertical + bottomRight.vertical, 1e-9),
    );
    return corners.map((corner) => ({ horizontal: corner.horizontal * factor, vertical: corner.vertical * factor }));
  };

  const near = (first, second) => Math.abs(first - second) <= 0.5;

  const geometryOf = (radii, width, height) => {
    if (radii.every((corner) => corner.horizontal <= 0.5 && corner.vertical <= 0.5)) return { geometry: "rect" };
    if (radii.every((corner) => corner.horizontal >= width / 2 - 0.5 && corner.vertical >= height / 2 - 0.5)) return { geometry: "ellipse" };
    if (!radii.every((corner) => near(corner.horizontal, corner.vertical))) return null;
    const [topLeft, topRight, bottomRight, bottomLeft] = radii.map((corner) => corner.horizontal);
    if (near(topLeft, topRight) && near(topLeft, bottomRight) && near(topLeft, bottomLeft)) return { geometry: "roundRect", radiusPx: round(topLeft) };
    if (near(topLeft, topRight) && near(bottomLeft, bottomRight)) return { geometry: "round2SameRect", radiusPx: round(topLeft), bottomRadiusPx: round(bottomLeft) };
    return null;
  };

  const paintOf = (color, opacity) => ({ color, opacity: round(opacity) });

  const relative = (rect, origin) => ({ left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) });

  const rulesOf = (sides, rect, opacity, origin) => {
    const [top, right, bottom, left] = sides;
    const rules = [];
    const rule = (side, from, to) => side.visible && rules.push({ geometry: "line", from, to, line: { ...paintOf(side.color, opacity), widthPx: round(side.width) } });
    rule(top, { x: rect.left - origin.left, y: rect.top + top.width / 2 - origin.top }, { x: rect.right - origin.left, y: rect.top + top.width / 2 - origin.top });
    rule(bottom, { x: rect.left - origin.left, y: rect.bottom - bottom.width / 2 - origin.top }, { x: rect.right - origin.left, y: rect.bottom - bottom.width / 2 - origin.top });
    rule(left, { x: rect.left + left.width / 2 - origin.left, y: rect.top - origin.top }, { x: rect.left + left.width / 2 - origin.left, y: rect.bottom - origin.top });
    rule(right, { x: rect.right - right.width / 2 - origin.left, y: rect.top - origin.top }, { x: rect.right - right.width / 2 - origin.left, y: rect.bottom - origin.top });
    return rules.map((shape) => ({ ...shape, from: { x: round(shape.from.x), y: round(shape.from.y) }, to: { x: round(shape.to.x), y: round(shape.to.y) } }));
  };

  const shapeInset = (rect, inset) => ({ left: rect.left + inset, top: rect.top + inset, right: rect.right - inset, bottom: rect.bottom - inset });

  const boxShapes = (item, rect, opacity, origin) => {
    const style = item.style;
    const hasFill = colorAlpha(style.backgroundColor) > 0;
    const sides = sidesOf(style);
    const visibleSides = sides.filter((side) => side.visible);
    const width = rect.right - rect.left;
    const height = rect.bottom - rect.top;
    const radii = cornerRadii(style, width, height);
    const shape = geometryOf(radii, width, height);
    if (!shape) return null;
    const fill = hasFill ? paintOf(style.backgroundColor, opacity) : null;
    const uniform = visibleSides.length === 4 && visibleSides.every((side) => side.lineStyle === "solid" && near(side.width, sides[0].width) && side.color === sides[0].color);
    if (!visibleSides.length || uniform) {
      const strokeWidth = uniform ? sides[0].width : 0;
      const line = uniform ? { ...paintOf(sides[0].color, opacity), widthPx: round(strokeWidth) } : null;
      const inset = strokeWidth / 2;
      return [{
        ...shape,
        ...(shape.radiusPx !== undefined ? { radiusPx: round(Math.max(0, shape.radiusPx - inset)) } : {}),
        ...(shape.bottomRadiusPx !== undefined ? { bottomRadiusPx: round(Math.max(0, shape.bottomRadiusPx - inset)) } : {}),
        box: relative(shapeInset(rect, inset), origin),
        fill,
        line,
      }];
    }
    if (shape.geometry !== "rect" || visibleSides.some((side) => side.lineStyle !== "solid")) return null;
    return [...(fill ? [{ geometry: "rect", box: relative(rect, origin), fill, line: null }] : []), ...rulesOf(sides, rect, opacity, origin)];
  };

  const inflateByShadow = (rect, boxShadow) => {
    if (!boxShadow || boxShadow === "none") return rect;
    const extent = Math.max(0, ...boxShadow.split(/,(?![^(]*\))/).map((shadow) => (shadow.match(/-?[\d.]+px/g) || []).reduce((sum, length) => sum + Math.abs(parseFloat(length)), 0)));
    return { left: rect.left - extent, top: rect.top - extent, right: rect.right + extent, bottom: rect.bottom + extent };
  };

  const paintsBox = (style) =>
    colorAlpha(style.backgroundColor) > 0 ||
    style.backgroundImage !== "none" ||
    style.boxShadow !== "none" ||
    (style.outlineStyle !== "none" && pixels(style.outlineWidth) > 0) ||
    sidesOf(style).some((side) => side.visible);

  const hasPictureOnlyPaint = (style) =>
    style.backgroundImage !== "none" || style.boxShadow !== "none" || (style.outlineStyle !== "none" && pixels(style.outlineWidth) > 0);

  const tableTags = new Set(["TABLE", "THEAD", "TBODY", "TFOOT", "TR", "TD", "TH"]);
  const hasCollapsedBorders = (item) => !item.pseudo && tableTags.has(item.element.tagName) && item.style.borderCollapse === "collapse" && sidesOf(item.style).some((side) => side.visible);

  const pseudoText = (style) => {
    const content = style.content;
    return content !== "none" && content !== "normal" && content !== '""' && content !== "''";
  };

  const classify = (item, section, origin) => {
    const style = item.style;
    if (nativeTableAttribute && item.element.closest(`[${nativeTableAttribute}]`)) return { kind: "none" };
    if (item.pseudo && style.visibility !== "visible") return { kind: "none" };
    const { rect, exact } = rectOf(item);
    if (isInsidePicture(item, section)) return { kind: "picture", rect: inflateByShadow(rect, style.boxShadow) };
    if (item.pseudo && pseudoText(style)) return { kind: "picture", rect };
    if (style.display === "contents" || !paintsBox(style) || rect.right <= rect.left || rect.bottom <= rect.top) return { kind: "none" };
    if (hasCollapsedBorders(item)) return { kind: "picture", rect };
    const opacity = opacityOf(item, section);
    if (opacity <= 0) return { kind: "none" };
    if (!exact || hasPictureOnlyPaint(style) || isClippedByAncestor(item, rect, section)) return { kind: "picture", rect: inflateByShadow(rect, style.boxShadow) };
    const shapes = boxShapes(item, rect, opacity, origin);
    return shapes ? { kind: "shape", rect, shapes } : { kind: "picture", rect };
  };

  const overlaps = (first, second) => first.left < second.right && second.left < first.right && first.top < second.bottom && second.top < first.bottom;

  let markCount = 0;
  const markExported = (item) => {
    markCount += 1;
    item.element.setAttribute(item.pseudo ? pseudoAttributes[item.pseudo] : exportedShapeAttribute, String(markCount));
  };

  const describeSlide = (section) => {
    const origin = section.getBoundingClientRect();
    const order = paintOrder({ element: section, pseudo: "", style: getComputedStyle(section) }).slice(1);
    const pictureRegions = [];
    const emitted = [];
    for (const item of order.reverse()) {
      const verdict = classify(item, section, origin);
      if (verdict.kind === "none") continue;
      if (verdict.kind === "shape" && !pictureRegions.some((region) => overlaps(region, verdict.rect))) {
        markExported(item);
        emitted.unshift(...verdict.shapes);
        continue;
      }
      pictureRegions.push(verdict.rect);
    }
    return { shapes: emitted, boxesKeptAsPicture: pictureRegions.length };
  };

  return pages.map(describeSlide);
}

export function hideExportedBoxes({ exportedShapeAttribute, exportedBeforeShapeAttribute, exportedAfterShapeAttribute }) {
  const hidden = "background-color: transparent !important; border-color: transparent !important;";
  const rules = [
    `[${exportedShapeAttribute}] { ${hidden} }`,
    `[${exportedBeforeShapeAttribute}]::before { ${hidden} }`,
    `[${exportedAfterShapeAttribute}]::after { ${hidden} }`,
  ];
  const stylesheet = document.createElement("style");
  stylesheet.textContent = rules.join("\n");
  document.head.appendChild(stylesheet);
}
