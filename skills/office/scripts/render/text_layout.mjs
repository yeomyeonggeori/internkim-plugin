export const exportedTextAttribute = "data-internkim-pptx-text";
export const exportedListAttribute = "data-internkim-pptx-list";
export const markerProbeAttribute = "data-internkim-pptx-marker";
export const markerProbeHostId = "internkim-pptx-marker-probes";

export function insertMarkerProbes({ markerProbeAttribute, markerProbeHostId, pages }) {
  const bulletCharacters = { disc: "•", circle: "◦", square: "▪" };
  const numberingSchemes = { decimal: "arabicPeriod", "decimal-leading-zero": "arabicPeriod", "lower-alpha": "alphaLcPeriod", "lower-latin": "alphaLcPeriod", "upper-alpha": "alphaUcPeriod", "upper-latin": "alphaUcPeriod", "lower-roman": "romanLcPeriod", "upper-roman": "romanUcPeriod" };
  const ordinalOf = (item) => (item.parentElement.start || 1) + Array.from(item.parentElement.children).filter((child) => child.tagName === "LI").indexOf(item);
  const markerTextOf = (item, style) => {
    if (style.listStyleType.startsWith('"')) return style.listStyleType.slice(1, -1);
    if (bulletCharacters[style.listStyleType]) return `${bulletCharacters[style.listStyleType]} `;
    if (numberingSchemes[style.listStyleType]) return `${ordinalOf(item)}. `;
    return "";
  };
  const host = document.createElement("div");
  host.id = markerProbeHostId;
  host.style.cssText = "position:absolute;left:0;top:0;visibility:hidden;pointer-events:none";
  pages.flatMap((page) => Array.from(page.querySelectorAll("li"))).forEach((item, index) => {
    const style = getComputedStyle(item);
    const markerText = markerTextOf(item, style);
    if (!markerText) return;
    const probe = document.createElement("span");
    probe.textContent = markerText;
    probe.dataset.numbering = numberingSchemes[style.listStyleType] || "";
    probe.setAttribute(markerProbeAttribute, String(index));
    const letterSpacing = style.letterSpacing === "normal" ? "" : `;letter-spacing:${style.letterSpacing}`;
    probe.style.cssText = `white-space:pre;font-family:${style.fontFamily};font-size:${style.fontSize};font-weight:${style.fontWeight};font-style:${style.fontStyle}${letterSpacing}`;
    item.setAttribute(markerProbeAttribute, String(index));
    host.appendChild(probe);
  });
  document.documentElement.appendChild(host);
}

export function renderedFamilyResolver() {
  const genericFamilies = new Set(["serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded", "-apple-system", "blinkmacsystemfont", "emoji", "math", "fangsong"]);
  const unquote = (name) => name.trim().replace(/^["']|["']$/g, "");
  const loadedFamilies = new Set();
  document.fonts.forEach((face) => {
    if (face.status === "loaded") loadedFamilies.add(unquote(face.family).toLowerCase());
  });
  return (fontFamilyList) => {
    const families = fontFamilyList.split(",").map(unquote).filter(Boolean);
    return families.find((family) => loadedFamilies.has(family.toLowerCase()))
      || families.find((family) => !genericFamilies.has(family.toLowerCase()))
      || families[0]
      || "sans-serif";
  };
}

export function extractTextLayout({ exportedTextAttribute, exportedListAttribute, markerProbeAttribute, markerProbeHostId, pages }) {
  const skippedTags = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "TEXTAREA", "SELECT", "OPTION"]);
  const linkProtocols = new Set(["http:", "https:", "mailto:", "tel:"]);
  const alignments = { left: "l", start: "l", right: "r", end: "r", center: "ctr", justify: "just", "-webkit-center": "ctr" };
  const edgeTolerance = 2;

  const round = (value) => Math.round(value * 100) / 100;
  const pixels = (value) => parseFloat(value) || 0;
  const renderedFamily = renderedFamilyResolver();

  const isInlineDisplay = (display) => display === "inline" || display === "contents";

  const blockContainerOf = (node, section) => {
    let element = node.parentElement;
    while (element && element !== section && isInlineDisplay(getComputedStyle(element).display)) {
      element = element.parentElement;
    }
    return element || section;
  };

  const hasOnlyTranslation = (transform) => {
    if (transform === "none") return true;
    const values = transform.match(/-?[\d.e]+/g)?.map(Number) || [];
    if (transform.startsWith("matrix(")) return values[0] === 1 && values[1] === 0 && values[2] === 0 && values[3] === 1;
    return false;
  };

  const drawsTextAsPicture = (style) =>
    !hasOnlyTranslation(style.transform) ||
    style.writingMode !== "horizontal-tb" ||
    (style.webkitBackgroundClip || style.backgroundClip) === "text" ||
    style.filter !== "none" ||
    style.mixBlendMode !== "normal";

  const textStateOf = (textNode, section) => {
    let opacity = 1;
    for (let element = textNode.parentElement; element; element = element.parentElement) {
      if (skippedTags.has(element.tagName) || element.classList.contains("notes")) return { skipped: true };
      if (element instanceof SVGElement || element.tagName === "MATH") return { picture: true };
      const style = getComputedStyle(element);
      if (style.display === "none") return { skipped: true };
      if (drawsTextAsPicture(style)) return { picture: true };
      opacity *= parseFloat(style.opacity);
      if (element === section) break;
    }
    const parentStyle = getComputedStyle(textNode.parentElement);
    if (parentStyle.visibility !== "visible" || opacity === 0) return { skipped: true };
    return { opacity };
  };

  const textRectsOf = (textNode) => {
    const range = document.createRange();
    range.selectNodeContents(textNode);
    return Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
  };

  const decorationsOf = (element, container) => {
    const lines = new Set();
    for (let current = element; current; current = current.parentElement) {
      getComputedStyle(current).textDecorationLine.split(" ").forEach((line) => lines.add(line));
      if (current === container) break;
    }
    return lines;
  };

  const linkOf = (element, section) => {
    const anchor = element.closest("a[href]");
    if (!anchor || !section.contains(anchor)) return null;
    const url = new URL(anchor.getAttribute("href"), document.baseURI);
    return linkProtocols.has(url.protocol) ? url.href : null;
  };

  const transformText = (text, textTransform, startsMidWord) => {
    if (textTransform === "uppercase") return text.toUpperCase();
    if (textTransform === "lowercase") return text.toLowerCase();
    if (textTransform === "capitalize" && startsMidWord) return transformText(`x${text}`, textTransform, false).slice(1);
    if (textTransform === "capitalize") return text.replace(/(^|\s)(\S)/g, (match, space, letter) => space + letter.toUpperCase());
    return text;
  };

  const collapseWhiteSpace = (text, whiteSpace) => {
    if (whiteSpace === "pre" || whiteSpace === "pre-wrap" || whiteSpace === "break-spaces") return text.replace(/\r\n?/g, "\n");
    if (whiteSpace === "pre-line") return text.replace(/[ \t]+/g, " ").replace(/ ?\n ?/g, "\n");
    return text.replace(/[ \t\n\r\f]+/g, " ");
  };

  const runOf = (textNode, container, section, opacity, segment) => {
    const element = textNode.parentElement;
    const style = getComputedStyle(element);
    const decorations = decorationsOf(element, container);
    const startsMidWord = segment.start > 0 && !/\s/.test(textNode.textContent[segment.start - 1]);
    const text = transformText(collapseWhiteSpace(segment.text, style.whiteSpace), style.textTransform, startsMidWord);
    return {
      text,
      fontFamily: renderedFamily(style.fontFamily),
      fontWeight: parseInt(style.fontWeight, 10) || 400,
      italic: style.fontStyle !== "normal",
      sizePx: round(pixels(style.fontSize)),
      color: style.webkitTextFillColor || style.color,
      opacity: round(opacity),
      letterSpacingPx: style.letterSpacing === "normal" ? 0 : round(pixels(style.letterSpacing)),
      underline: decorations.has("underline"),
      strike: decorations.has("line-through"),
      baseline: style.verticalAlign === "super" ? "super" : style.verticalAlign === "sub" ? "sub" : "",
      href: linkOf(element, section),
    };
  };

  const lineBoxOf = (rect, lineHeightPx) => {
    const halfLeading = lineHeightPx ? (lineHeightPx - rect.height) / 2 : 0;
    return { top: rect.top - halfLeading, bottom: rect.bottom + halfLeading, left: rect.left, right: rect.right, halfLeading };
  };

  const lineHeightOf = (style) => (style.lineHeight === "normal" ? 0 : pixels(style.lineHeight));

  const unionOf = (rects) => ({
    left: Math.min(...rects.map((rect) => rect.left)),
    top: Math.min(...rects.map((rect) => rect.top)),
    right: Math.max(...rects.map((rect) => rect.right)),
    bottom: Math.max(...rects.map((rect) => rect.bottom)),
  });

  const boxesOf = (element) => {
    const style = getComputedStyle(element);
    const border = element.getBoundingClientRect();
    const padding = {
      left: border.left + pixels(style.borderLeftWidth),
      top: border.top + pixels(style.borderTopWidth),
      right: border.right - pixels(style.borderRightWidth),
      bottom: border.bottom - pixels(style.borderBottomWidth),
    };
    const insets = { left: pixels(style.paddingLeft), top: pixels(style.paddingTop), right: pixels(style.paddingRight), bottom: pixels(style.paddingBottom) };
    const content = { left: padding.left + insets.left, top: padding.top + insets.top, right: padding.right - insets.right, bottom: padding.bottom - insets.bottom };
    return { padding, content, insets };
  };

  const collectTextNodes = (section) => {
    const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
    const pieces = [];
    const pictureTexts = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const state = textStateOf(node, section);
      if (state.skipped) continue;
      if (state.picture) {
        if (node.textContent.trim()) pictureTexts.push(node.textContent.trim());
        continue;
      }
      const rects = textRectsOf(node);
      if (!rects.length && node.textContent.trim()) continue;
      pieces.push({ node, rects, opacity: state.opacity, container: blockContainerOf(node, section) });
    }
    return { pieces, pictureTexts };
  };

  const breaksLine = (element) => !/(flex|grid)$/.test(getComputedStyle(element.parentElement).display);

  const breaksIn = (section) =>
    Array.from(section.querySelectorAll("br"))
      .filter(breaksLine)
      .map((element) => ({ node: element, isBreak: true, container: blockContainerOf(element, section) }));

  const documentOrder = (first, second) => (first.node.compareDocumentPosition(second.node) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1);

  const trimParagraphRuns = (runs) => {
    const joined = [];
    for (const run of runs) {
      const previous = joined[joined.length - 1];
      let text = run.text;
      const followsSpace = !previous || previous.isBreak || /[ \n]$/.test(previous.text);
      if (!run.isBreak && followsSpace && run.collapsible) text = text.replace(/^ /, "");
      if (!run.isBreak && !text) continue;
      joined.push({ ...run, text });
    }
    for (let index = 0; index < joined.length; index += 1) {
      const next = joined[index + 1];
      if (joined[index].collapsible && (!next || next.isBreak)) joined[index].text = joined[index].text.replace(/ $/, "");
    }
    return joined.filter((run) => run.isBreak || run.text).map(({ collapsible, ...run }) => run);
  };

  const isLowSurrogate = (code) => code >= 0xdc00 && code <= 0xdfff;

  const characterRectOf = (range, node, offset) => {
    const end = offset + 1 < node.textContent.length && isLowSurrogate(node.textContent.charCodeAt(offset + 1)) ? offset + 2 : offset + 1;
    range.setStart(node, offset);
    range.setEnd(node, end);
    const rects = Array.from(range.getClientRects()).filter((rect) => rect.width > 0 && rect.height > 0);
    return rects[rects.length - 1] || null;
  };

  const measureVisualLines = (items) => {
    const range = document.createRange();
    const lineStarts = new Map();
    const lines = [];
    let current = null;
    let followsExplicitBreak = true;
    for (const item of items) {
      if (item.isBreak) {
        current = null;
        followsExplicitBreak = true;
        continue;
      }
      const text = item.node.textContent;
      const style = getComputedStyle(item.node.parentElement);
      const sizePx = pixels(style.fontSize);
      const keepsNewlines = style.whiteSpace !== "normal" && style.whiteSpace !== "nowrap";
      for (let offset = 0; offset < text.length; offset += 1) {
        if (isLowSurrogate(text.charCodeAt(offset))) continue;
        if (keepsNewlines && text[offset] === "\n") {
          current = null;
          followsExplicitBreak = true;
          continue;
        }
        if (/\s/.test(text[offset])) {
          if (current && !current.text.endsWith(" ")) current.text += " ";
          continue;
        }
        const rect = characterRectOf(range, item.node, offset);
        if (!rect) continue;
        const center = rect.top + rect.height / 2;
        if (!current || center > current.bottom) {
          if (current && !followsExplicitBreak) {
            if (!lineStarts.has(item.node)) lineStarts.set(item.node, []);
            lineStarts.get(item.node).push(offset);
          }
          current = { left: rect.left, right: rect.right, bottom: rect.bottom, sizePx, text: "" };
          lines.push(current);
          followsExplicitBreak = false;
        }
        current.left = Math.min(current.left, rect.left);
        current.right = Math.max(current.right, rect.right);
        current.bottom = Math.max(current.bottom, rect.bottom);
        current.sizePx = Math.max(current.sizePx, sizePx);
        current.text += text.slice(offset, isLowSurrogate(text.charCodeAt(offset + 1)) ? offset + 2 : offset + 1);
      }
    }
    return { lineStarts, lines: lines.map((line) => ({ widthPx: round(line.right - line.left), sizePx: round(line.sizePx), text: line.text.trim() })) };
  };

  const segmentsOf = (node, starts) => {
    const text = node.textContent;
    const boundaries = [0, ...starts, text.length];
    return boundaries.slice(0, -1).map((start, index) => ({ start, text: text.slice(start, boundaries[index + 1]) }));
  };

  const paragraphRunsOf = (items, container, section, lineStarts) => {
    const runs = items.flatMap((item) => {
      if (item.isBreak) return [{ isBreak: true, text: "" }];
      const whiteSpace = getComputedStyle(item.node.parentElement).whiteSpace;
      const collapsible = !whiteSpace.startsWith("pre") && whiteSpace !== "break-spaces";
      return segmentsOf(item.node, lineStarts.get(item.node) || []).flatMap((segment, index) => [
        ...(index > 0 ? [{ isBreak: true, text: "" }] : []),
        { ...runOf(item.node, container, section, item.opacity, segment), collapsible },
      ]);
    });
    const trimmed = trimParagraphRuns(runs);
    while (trimmed.length && trimmed[trimmed.length - 1].isBreak) trimmed.pop();
    return trimmed.flatMap((run) => (run.isBreak ? [run] : splitNewlines(run)));
  };

  const splitNewlines = (run) =>
    run.text.split("\n").flatMap((part, index) => (index === 0 ? [{ ...run, text: part }] : [{ isBreak: true, text: "" }, { ...run, text: part }])).filter((part) => part.isBreak || part.text);

  const alignmentOf = (style) => alignments[style.textAlign] || "l";

  const measuredAlignment = (declared, lines, content) => {
    const gapLeft = lines.left - content.left;
    const gapRight = content.right - lines.right;
    if (gapLeft <= edgeTolerance && declared !== "ctr" && declared !== "r") return declared;
    if (Math.abs(gapLeft - gapRight) <= edgeTolerance) return "ctr";
    if (gapRight <= edgeTolerance) return "r";
    return declared;
  };

  const measuredAnchor = (lines, content) => {
    const gapTop = lines.top - content.top;
    const gapBottom = content.bottom - lines.bottom;
    if (gapTop <= edgeTolerance) return "t";
    if (Math.abs(gapTop - gapBottom) <= edgeTolerance) return "ctr";
    if (gapBottom <= edgeTolerance) return "b";
    return "";
  };

  const lineCountOf = (rects) => {
    const centers = rects.map((rect) => ({ center: rect.top + rect.height / 2, height: rect.height })).sort((first, second) => first.center - second.center);
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

  const relativeTo = (rect, origin) => ({ left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) });

  const measuredParagraphContent = (items, container, section) => {
    const { lineStarts, lines } = measureVisualLines(items);
    return { runs: paragraphRunsOf(items, container, section, lineStarts), lines };
  };

  const paragraphOf = (items, container, section, properties) => ({ ...properties, ...measuredParagraphContent(items, container, section) });

  const describeBlock = (container, items, section, isPure) => {
    const style = getComputedStyle(container);
    const lineHeightPx = lineHeightOf(style);
    const rects = items.flatMap((item) => item.rects || []);
    const lineBoxes = rects.map((rect) => lineBoxOf(rect, lineHeightPx));
    const lines = unionOf(lineBoxes);
    const { padding, content, insets } = boxesOf(container);
    const declaredAlignment = alignmentOf(style);
    const singleLine = lineCountOf(rects) === 1;
    const anchor = isPure ? measuredAnchor(lines, content) : "";
    const fitsContent = isPure && anchor;
    const alignment = isPure && singleLine ? measuredAlignment(declaredAlignment, lines, content) : declaredAlignment;
    const textLeft = alignment === "l" ? Math.max(content.left, lines.left) : content.left;
    const box = fitsContent ? padding : { left: textLeft, right: content.right, top: lines.top, bottom: lines.bottom };
    return {
      box,
      insets: fitsContent ? insets : { left: 0, top: 0, right: 0, bottom: 0 },
      anchor: anchor || "t",
      noWrap: singleLine || style.whiteSpace === "nowrap" || style.whiteSpace === "pre",
      keepWords: style.wordBreak === "keep-all",
      firstLineHalfLeading: round(lineBoxes[0].halfLeading),
      paragraphs: [paragraphOf(items, container, section, { alignment, lineHeightPx: round(lineHeightPx), spaceBeforePx: 0, bullet: null })],
    };
  };

  const markerProbes = new Map(Array.from(document.querySelectorAll(`#${markerProbeHostId} [${markerProbeAttribute}]`), (probe) => [probe.getAttribute(markerProbeAttribute), probe]));

  const bulletOf = (item) => {
    const probe = markerProbes.get(item.getAttribute(markerProbeAttribute));
    if (!probe) return null;
    const style = getComputedStyle(item);
    const numbering = probe.dataset.numbering;
    return {
      character: numbering ? "" : probe.textContent.trim(),
      numbering,
      startAt: numbering ? item.parentElement.start || 1 : 0,
      color: getComputedStyle(item, "::marker").color || style.color,
      outside: style.listStylePosition === "outside",
      markerWidthPx: round(probe.getBoundingClientRect().width),
    };
  };

  const describeList = (list, listItems, itemsByContainer, section) => {
    const paragraphs = [];
    const boxes = [];
    let previousBottom = null;
    let firstHalfLeading = 0;
    for (const item of listItems) {
      const style = getComputedStyle(item);
      const lineHeightPx = lineHeightOf(style);
      const items = itemsByContainer.get(item);
      const lineBoxes = items.flatMap((entry) => entry.rects || []).map((rect) => lineBoxOf(rect, lineHeightPx));
      const lines = unionOf(lineBoxes);
      const { content } = boxesOf(item);
      const bullet = bulletOf(item);
      const hangingWidth = bullet && bullet.outside ? bullet.markerWidthPx : 0;
      boxes.push({ left: content.left - hangingWidth, right: content.right, top: lines.top, bottom: lines.bottom, contentLeft: content.left, hangingWidth });
      if (previousBottom === null) firstHalfLeading = lineBoxes[0].halfLeading;
      paragraphs.push({
        alignment: alignmentOf(style),
        lineHeightPx: round(lineHeightPx),
        spaceBeforePx: previousBottom === null ? 0 : round(Math.max(0, lines.top - previousBottom)),
        bullet,
        ...measuredParagraphContent(items, item, section),
      });
      previousBottom = lines.bottom;
    }
    const box = unionOf(boxes);
    paragraphs.forEach((paragraph, index) => {
      paragraph.marginLeftPx = round(boxes[index].contentLeft - box.left);
      paragraph.indentPx = round(-boxes[index].hangingWidth);
    });
    return {
      box,
      insets: { left: 0, top: 0, right: 0, bottom: 0 },
      anchor: "t",
      noWrap: false,
      keepWords: getComputedStyle(list).wordBreak === "keep-all",
      firstLineHalfLeading: round(firstHalfLeading),
      paragraphs,
    };
  };

  const exportableList = (list, containers, itemsByContainer) => {
    if (!list || !/^(UL|OL)$/.test(list.tagName) || itemsByContainer.has(list)) return null;
    const listItems = Array.from(list.children).filter((child) => child.tagName === "LI");
    if (!listItems.length || !listItems.every((item) => itemsByContainer.has(item))) return null;
    const hasNestedText = containers.some((container) => container !== list && list.contains(container) && !listItems.includes(container));
    return hasNestedText ? null : listItems;
  };

  let markCount = 0;
  const markExported = (items) => {
    for (const item of items) {
      if (item.isBreak || item.node.parentElement.hasAttribute(exportedTextAttribute)) continue;
      markCount += 1;
      item.node.parentElement.setAttribute(exportedTextAttribute, String(markCount));
    }
  };

  const describeSlide = (section) => {
    const origin = section.getBoundingClientRect();
    const { pieces, pictureTexts } = collectTextNodes(section);
    const items = [...pieces, ...breaksIn(section).filter((entry) => pieces.some((piece) => piece.container === entry.container))].sort(documentOrder);
    const itemsByContainer = new Map();
    for (const item of items) {
      if (!itemsByContainer.has(item.container)) itemsByContainer.set(item.container, []);
      itemsByContainer.get(item.container).push(item);
    }
    for (const [container, entries] of itemsByContainer) {
      if (!entries.some((entry) => !entry.isBreak && entry.node.textContent.trim())) itemsByContainer.delete(container);
    }
    const containers = Array.from(itemsByContainer.keys());
    const handledLists = new Set();
    const blocks = [];
    for (const container of containers) {
      const list = container.tagName === "LI" ? container.parentElement : null;
      if (handledLists.has(list)) continue;
      const listItems = exportableList(list, containers, itemsByContainer);
      if (listItems) {
        handledLists.add(list);
        list.setAttribute(exportedListAttribute, "");
        listItems.forEach((item) => markExported(itemsByContainer.get(item)));
        blocks.push(describeList(list, listItems, itemsByContainer, section));
        continue;
      }
      const isPure = !containers.some((other) => other !== container && container.contains(other));
      markExported(itemsByContainer.get(container));
      blocks.push(describeBlock(container, itemsByContainer.get(container), section, isPure));
    }
    return {
      width: round(origin.width),
      height: round(origin.height),
      visibleText: section.innerText,
      pictureTexts,
      blocks: blocks
        .map((block) => ({ ...block, box: relativeTo(block.box, origin) }))
        .filter((block) => block.paragraphs.some((paragraph) => paragraph.runs.some((run) => run.text.trim()))),
    };
  };

  const slides = pages.map(describeSlide);
  document.getElementById(markerProbeHostId)?.remove();
  return { language: document.documentElement.lang, slides };
}

export function hideExportedText({ exportedTextAttribute, exportedListAttribute }) {
  const hiddenDeclarations = "-webkit-text-fill-color: transparent !important; text-shadow: none !important; -webkit-text-stroke-width: 0 !important; text-decoration-color: transparent !important;";
  const kept = (style) => `-webkit-text-fill-color: ${style.webkitTextFillColor || style.color} !important; text-shadow: ${style.textShadow} !important;`;
  const rules = [`[${exportedListAttribute}] > li::marker { color: transparent !important; -webkit-text-fill-color: transparent !important; }`];
  const frozenDescendants = [];
  for (const element of document.querySelectorAll(`[${exportedTextAttribute}]`)) {
    const selector = `[${exportedTextAttribute}="${element.getAttribute(exportedTextAttribute)}"]`;
    rules.push(`${selector} { ${hiddenDeclarations} }`);
    for (const pseudo of ["::before", "::after"]) {
      const style = getComputedStyle(element, pseudo);
      if (style.content !== "none" && style.content !== "normal") rules.push(`${selector}${pseudo} { ${kept(style)} }`);
    }
    if (getComputedStyle(element).display === "list-item" && !element.parentElement?.hasAttribute(exportedListAttribute)) {
      rules.push(`${selector}::marker { ${kept(getComputedStyle(element, "::marker"))} }`);
    }
    for (const descendant of element.querySelectorAll(`*:not([${exportedTextAttribute}])`)) {
      frozenDescendants.push([descendant, getComputedStyle(descendant)]);
    }
  }
  const frozen = frozenDescendants.map(([element, style]) => [element, style.webkitTextFillColor || style.color, style.textShadow]);
  frozen.forEach(([element, fillColor, textShadow]) => {
    element.style.setProperty("-webkit-text-fill-color", fillColor, "important");
    element.style.setProperty("text-shadow", textShadow, "important");
  });
  const stylesheet = document.createElement("style");
  stylesheet.textContent = rules.join("\n");
  document.head.appendChild(stylesheet);
}
