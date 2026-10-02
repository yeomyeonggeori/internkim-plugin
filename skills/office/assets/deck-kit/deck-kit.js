(() => {
  const fitSteps = [1, 0.95, 0.9, 0.86, 0.82, 0.78];
  const growSteps = [1.3, 1.2, 1.1, 1];
  const growingLayouts = new Set(["kpi", "cards", "comparison", "table"]);
  const itemSlackShare = 0.15;
  const boundedAttribute = "data-kit-bounded";
  const overflowTolerance = 2;
  const titleLineMaximum = 3;
  const balanceSteps = 7;
  const clauseEndPattern = /[,，、·:;]$/;
  const phraseBreakPenalty = 0.35;
  const footerlessLayouts = new Set(["cover", "section"]);
  const itemClasses = ["kpi", "card", "step", "column"];
  const rowItemClasses = ["kpi", "card", "column"];
  const alignedAttribute = "data-kit-aligned";
  const numberFrameSelector = ".eyebrow, h2, .lead, .value, .label, .takeaway, .source, .kit-footer, aside";
  const gridCardCount = 4;
  const capacityAttribute = "data-kit-capacity";
  const connectorLayerAttribute = "data-native-connectors";
  const diagramGapShare = 4.5;
  const arrowLength = 16;
  const arrowWidth = 14;
  const connectorWidth = 2.5;
  const cycleRadii = { x: 35, y: 37 };
  const cycleNodeWidth = 24;
  const cycleSlotHeight = 26;
  const hierarchySlotShare = 0.6;
  const hierarchyNodeShare = 0.86;
  const hierarchyNodeLimit = 22;
  const pyramidWidths = { top: 34, bottom: 96 };
  const pyramidGapShare = 3;
  const processHeight = 62;
  const matrixAxisInset = { left: 4, bottom: 9 };
  const matrixGapShare = 2;
  const capacityPartNames = [["h1, h2", "title"], [".lead", "lead"], [".eyebrow", "eyebrow"], [".takeaway", "takeaway"], [".card", "card"], [".kpi", "kpi"], [".column", "column"], [".step", "step"], [".kit-steps", "steps"], [".insight", "insight"], ["ol, ul", "list"], ["table", "table"], ["figure", "chart"], ["blockquote", "quote"], [".kit-diagram", "diagram"]];
  const hangulPattern = /[\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF]/;
  const hangulRunPattern = /([\u1100-\u11FF\u3130-\u318F\uAC00-\uD7AF]+)/;
  const tightTrackingShare = -0.012;
  const untrackedSelector = "aside, svg, script, style";
  const unitWordPattern = /^[\uAC00-\uD7AF][^\s\d\uAC00-\uD7AF]*$/;
  const keptInlineSelector = "em, strong, b, i, mark, small, span, a";
  const phrasingSelector = "em, strong, b, i, mark, a, span, code, sub, sup";
  const unkeptSelector = "aside, figure, table, svg, script, style, .kit-keep";
  const firstQuantityColumn = 1;
  const numericCellPattern = /^[+\-−]?[₩$€£¥]?\s?[\d.,]+\s?(%p|%|[^\s\d()]{1,4}(\s[^\s\d()]{1,2})?)?(\s?\([^)]*\))?$/;
  const svgNamespace = "http://www.w3.org/2000/svg";
  const barScaleShare = 0.84;
  const barBandFill = 0.6;
  const clusterBandFill = 0.72;
  const clusterGapShare = 0.12;
  const barDepthShare = 0.4;
  const chartShareMinimum = 0.5;
  const chartFitPasses = 3;
  const chartFitTolerance = 24;
  const roundSideMinimum = 480;
  const columnKinds = new Set(["column", "stacked", "stacked100", "combo"]);
  const roundKinds = new Set(["donut", "pie"]);
  const lineInsetShare = 5;
  const coverRingRadii = [442, 342, 242];
  const groupedNumberPattern = /^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$/;
  const twoAxisTypes = new Set(["combo", "scatter"]);
  const comboColumnShare = 0.6;
  const comboLineBand = [0.68, 0.92];
  const insideLabelSeries = 3;
  const insideLabelInks = ["var(--on-accent)", "var(--ink)", "var(--bg)"];
  const scatterLabelSwitchShare = 70;
  const edgeTickClasses = { 0: "kit-from-start", 100: "kit-from-end" };
  const tickIntervals = 4;
  const roundStepMultiples = [1, 2, 5, 10];
  const iconAttribute = "data-icon";
  const iconHostClasses = ["card", "kpi", "step"];
  const iconListLayouts = ["agenda", "closing"];
  const nativeIconAttribute = "data-native-icon";

  function slides() {
    return Array.from(document.querySelectorAll("section[data-layout]"));
  }

  function directChildren(slide, className) {
    return Array.from(slide.children).filter((child) => child.classList.contains(className));
  }

  function locale() {
    return document.documentElement.getAttribute("lang") || "ko-KR";
  }

  function element(tag, className, style) {
    const created = document.createElement(tag);
    if (className) created.className = className;
    if (style) Object.entries(style).forEach(([name, value]) => created.style.setProperty(name, value));
    return created;
  }

  function svgElement(tag, attributes) {
    const created = document.createElementNS(svgNamespace, tag);
    Object.entries(attributes).forEach(([name, value]) => created.setAttribute(name, String(value)));
    return created;
  }

  function svgLayer(color, viewBox, preserveAspectRatio, shapes) {
    const layer = element("div", "kit-svg-layer", { color });
    const svg = svgElement("svg", { viewBox, preserveAspectRatio });
    shapes.forEach((shape) => svg.appendChild(shape));
    layer.appendChild(svg);
    return layer;
  }

  function percent(value) {
    return `${Math.round(value * 1000) / 1000}%`;
  }

  function addFooters() {
    const all = Array.from(document.querySelectorAll("section"));
    const deckLabel = document.body.getAttribute("data-footer") ?? document.title ?? "";
    slides().forEach((slide) => {
      if (footerlessLayouts.has(slide.getAttribute("data-layout")) || directChildren(slide, "kit-footer").length) return;
      const footer = element("footer", "kit-footer");
      directChildren(slide, "source").forEach((source) => footer.appendChild(source));
      const label = element("span", "kit-deck");
      label.textContent = deckLabel;
      footer.appendChild(label);
      const page = element("span", "kit-page");
      page.textContent = String(all.indexOf(slide) + 1).padStart(2, "0");
      footer.appendChild(page);
      slide.insertBefore(footer, directChildren(slide, "notes")[0] || null);
    });
  }

  function markStructure() {
    slides().forEach((slide) => {
      const itemCount = Math.max(...itemClasses.map((className) => directChildren(slide, className).length));
      if (itemCount > 1) slide.style.setProperty("--n", String(itemCount));
      if (slide.getAttribute("data-layout") === "cards") arrangeCardGrid(slide);
      if (slide.getAttribute("data-layout") === "closing" && directChildren(slide, "card").length) slide.classList.add("kit-carded");
      if (directChildren(slide, "insight").length) slide.classList.add("kit-with-insight");
      if (slide.getAttribute("data-layout") === "number") arrangeNumber(slide);
      slide.querySelectorAll("ol, ul").forEach((list) => list.style.setProperty("--items", String(listItems(list).length)));
      const hasBody = Array.from(slide.children).some((child) => child.classList.contains("card") || ["OL", "UL"].includes(child.tagName));
      if (!hasBody) slide.classList.add("kit-bare");
    });
  }

  function arrangeNumber(slide) {
    const support = Array.from(slide.children).filter((child) => !child.matches(numberFrameSelector));
    support.forEach((child) => child.classList.add("kit-support"));
    if (support.length) return;
    slide.classList.add("kit-lone");
    [...directChildren(slide, "value"), ...directChildren(slide, "label")].forEach(groupPhrasing);
    if (!directChildren(slide, "label").length) slide.classList.add("kit-unlabelled");
  }

  function arrangeCardGrid(slide) {
    const cards = directChildren(slide, "card");
    if (cards.length !== gridCardCount) return;
    slide.classList.add("kit-grid");
    slide.style.setProperty("--n", String(gridCardCount / 2));
    cards.slice(gridCardCount / 2).forEach((card) => card.classList.add("kit-second-row"));
    cards.filter((card) => card.firstElementChild?.matches(".label, .value")).forEach((card) => {
      card.classList.add("kit-keyed");
      card.firstElementChild.classList.add("kit-key");
    });
  }

  function diagramList(slide) {
    return Array.from(slide.children).find((child) => ["OL", "UL"].includes(child.tagName)) || null;
  }

  function listItems(list) {
    return list ? Array.from(list.children).filter((child) => child.tagName === "LI") : [];
  }

  function nestedList(item) {
    return Array.from(item.children).find((child) => ["OL", "UL"].includes(child.tagName)) || null;
  }

  function nodeFor(item, index) {
    const node = element("div", "kit-node");
    if (item.classList.contains("pick")) node.classList.add("pick");
    if (index !== null) {
      const number = element("span", "kit-index");
      number.textContent = String(index + 1).padStart(2, "0");
      node.appendChild(number);
    }
    Array.from(item.childNodes).filter((child) => !["OL", "UL"].includes(child.tagName)).forEach((child) => node.appendChild(child.cloneNode(true)));
    groupPhrasing(node);
    return node;
  }

  function placed(node, x, y, width, height, filled) {
    const slot = element("div", filled ? "kit-slot kit-filled" : "kit-slot", { left: percent(x - width / 2), top: percent(y - height / 2), width: percent(width), height: percent(height) });
    slot.appendChild(node);
    return slot;
  }

  function chain(slots, sides, closed) {
    const nodes = slots.map((slot) => slot.firstElementChild);
    const links = nodes.slice(1).map((node, index) => ({ from: nodes[index], to: node, sides, elbow: false }));
    return closed ? [...links, { from: nodes[nodes.length - 1], to: nodes[0], sides, elbow: false }] : links;
  }

  function planProcess(items) {
    const width = (100 - diagramGapShare * (items.length - 1)) / items.length;
    const nodes = items.map((item, index) => placed(nodeFor(item, index), index * (width + diagramGapShare) + width / 2, 50, width, processHeight, true));
    return { nodes, links: chain(nodes, ["right", "left"], false), axes: [] };
  }

  function planCycle(items) {
    const nodes = items.map((item, index) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * index) / items.length;
      return placed(nodeFor(item, index), 50 + cycleRadii.x * Math.cos(angle), 50 + cycleRadii.y * Math.sin(angle), cycleNodeWidth, cycleSlotHeight, false);
    });
    return { nodes, links: chain(nodes, null, true), axes: [] };
  }

  function treeOf(item, depth) {
    return { item, depth, children: listItems(nestedList(item)).map((child) => treeOf(child, depth + 1)) };
  }

  function leavesOf(tree) {
    return tree.children.length ? tree.children.flatMap(leavesOf) : [tree];
  }

  function depthOf(tree) {
    return Math.max(tree.depth, ...tree.children.map(depthOf));
  }

  function planHierarchy(items) {
    const roots = items.map((item) => treeOf(item, 0));
    const leaves = roots.flatMap(leavesOf);
    const levels = Math.max(...roots.map(depthOf)) + 1;
    const slot = 100 / leaves.length;
    const nodes = [];
    const links = [];
    const place = (tree) => {
      const children = tree.children.map(place);
      const x = children.length ? (children[0].x + children[children.length - 1].x) / 2 : (leaves.indexOf(tree) + 0.5) * slot;
      const node = nodeFor(tree.item, null);
      node.classList.add(`kit-level-${tree.depth + 1}`);
      nodes.push(placed(node, x, ((tree.depth + 0.5) / levels) * 100, Math.min(slot * hierarchyNodeShare, hierarchyNodeLimit), (100 / levels) * hierarchySlotShare, false));
      children.forEach((child) => links.push({ from: node, to: child.node, sides: ["bottom", "top"], elbow: true }));
      return { node, x };
    };
    roots.forEach(place);
    return { nodes, links, axes: [] };
  }

  function planPyramid(items) {
    const height = (100 - pyramidGapShare * (items.length - 1)) / items.length;
    const step = items.length > 1 ? (pyramidWidths.bottom - pyramidWidths.top) / (items.length - 1) : 0;
    const nodes = items.map((item, index) => placed(nodeFor(item, null), 50, index * (height + pyramidGapShare) + height / 2, pyramidWidths.top + step * index, height, true));
    return { nodes, links: [], axes: [] };
  }

  function planMatrix(items, list) {
    const hasAxes = list.hasAttribute("data-x") || list.hasAttribute("data-y");
    const inset = hasAxes ? matrixAxisInset : { left: 0, bottom: 0 };
    const width = (100 - inset.left - matrixGapShare) / 2;
    const height = (100 - inset.bottom - matrixGapShare) / 2;
    const nodes = items.map((item, index) => {
      const column = index % 2;
      const row = Math.floor(index / 2);
      return placed(nodeFor(item, null), inset.left + column * (width + matrixGapShare) + width / 2, row * (height + matrixGapShare) + height / 2, width, height, true);
    });
    const origin = { x: inset.left / 2, y: 100 - inset.bottom + matrixGapShare };
    const axes = hasAxes ? [{ start: origin, end: { x: origin.x, y: 0 } }, { start: origin, end: { x: 100, y: origin.y } }] : [];
    return { nodes, links: [], axes, labels: hasAxes ? matrixLabels(list) : [] };
  }

  function matrixLabels(list) {
    return [["data-y", "kit-axis-y"], ["data-x", "kit-axis-x"]]
      .filter(([attribute]) => list.getAttribute(attribute))
      .map(([attribute, className]) => {
        const label = element("p", `kit-axis-label ${className}`);
        label.textContent = list.getAttribute(attribute);
        return label;
      });
  }

  const diagramPlanners = {
    process: (items) => planProcess(items),
    cycle: (items) => planCycle(items),
    hierarchy: (items) => planHierarchy(items),
    pyramid: (items) => planPyramid(items),
    matrix: (items, list) => planMatrix(items, list),
  };

  function buildDiagrams() {
    slides().forEach((slide) => {
      const planner = diagramPlanners[slide.getAttribute("data-layout")];
      const list = diagramList(slide);
      if (!planner || !list || directChildren(slide, "kit-diagram").length) return;
      const plan = planner(listItems(list), list);
      const diagram = element("div", "kit-diagram");
      plan.nodes.forEach((node) => diagram.appendChild(node));
      (plan.labels || []).forEach((label) => diagram.appendChild(label));
      diagram.kitLinks = plan.links;
      diagram.kitAxes = plan.axes;
      list.classList.add("kit-source");
      slide.insertBefore(diagram, list);
    });
  }

  function slideScale(slide) {
    return slide.getBoundingClientRect().width / (slide.offsetWidth || slide.getBoundingClientRect().width || 1);
  }

  function boxWithin(target, slide) {
    const scale = slideScale(slide);
    const frame = slide.getBoundingClientRect();
    const rect = target.getBoundingClientRect();
    return { left: (rect.left - frame.left) / scale, top: (rect.top - frame.top) / scale, right: (rect.right - frame.left) / scale, bottom: (rect.bottom - frame.top) / scale };
  }

  function sidePoint(box, side) {
    const middle = { x: (box.left + box.right) / 2, y: (box.top + box.bottom) / 2 };
    return { top: { x: middle.x, y: box.top }, bottom: { x: middle.x, y: box.bottom }, left: { x: box.left, y: middle.y }, right: { x: box.right, y: middle.y } }[side];
  }

  function facingSides(first, second) {
    const horizontalGap = Math.max(second.left - first.right, first.left - second.right);
    const verticalGap = Math.max(second.top - first.bottom, first.top - second.bottom);
    if (verticalGap > horizontalGap) return second.top >= first.bottom ? ["bottom", "top"] : ["top", "bottom"];
    return second.left >= first.right ? ["right", "left"] : ["left", "right"];
  }

  function linkConnector(link, slide) {
    const first = boxWithin(link.from, slide);
    const second = boxWithin(link.to, slide);
    const sides = link.sides || facingSides(first, second);
    return { from: link.from, to: link.to, sides, elbow: link.elbow, arrow: "end", start: sidePoint(first, sides[0]), end: sidePoint(second, sides[1]) };
  }

  function axisConnector(axis, diagramBox) {
    const at = (point) => ({ x: diagramBox.left + ((diagramBox.right - diagramBox.left) * point.x) / 100, y: diagramBox.top + ((diagramBox.bottom - diagramBox.top) * point.y) / 100 });
    return { from: null, to: null, sides: null, elbow: false, arrow: "end", start: at(axis.start), end: at(axis.end) };
  }

  function connectorPoints(connector) {
    if (!connector.elbow) return [connector.start, connector.end];
    const middle = (connector.start.y + connector.end.y) / 2;
    return [connector.start, { x: connector.start.x, y: middle }, { x: connector.end.x, y: middle }, connector.end];
  }

  function arrowHead(points) {
    const tip = points[points.length - 1];
    const before = points[points.length - 2];
    const length = Math.hypot(tip.x - before.x, tip.y - before.y) || 1;
    const along = { x: (tip.x - before.x) / length, y: (tip.y - before.y) / length };
    const base = { x: tip.x - along.x * arrowLength, y: tip.y - along.y * arrowLength };
    const across = { x: -along.y * (arrowWidth / 2), y: along.x * (arrowWidth / 2) };
    return [tip, { x: base.x + across.x, y: base.y + across.y }, { x: base.x - across.x, y: base.y - across.y }];
  }

  function pointList(points, origin) {
    return points.map((point) => `${Math.round((point.x - origin.left) * 100) / 100},${Math.round((point.y - origin.top) * 100) / 100}`).join(" ");
  }

  function connectorShapes(connector, origin) {
    const points = connectorPoints(connector);
    const line = svgElement("polyline", { points: pointList(points, origin), fill: "none", stroke: "currentColor", "stroke-width": connectorWidth, "stroke-linejoin": "round" });
    const head = svgElement("polygon", { points: pointList(arrowHead(points), origin), fill: "currentColor" });
    return [line, head];
  }

  function drawConnectors(slide) {
    directChildren(slide, "kit-diagram").forEach((diagram) => {
      Array.from(diagram.children).filter((child) => child.hasAttribute(connectorLayerAttribute)).forEach((layer) => layer.remove());
      const diagramBox = boxWithin(diagram, slide);
      const connectors = [...(diagram.kitLinks || []).map((link) => linkConnector(link, slide)), ...(diagram.kitAxes || []).map((axis) => axisConnector(axis, diagramBox))];
      if (!connectors.length) return;
      const width = diagramBox.right - diagramBox.left;
      const height = diagramBox.bottom - diagramBox.top;
      const layer = svgLayer("var(--muted)", `0 0 ${width} ${height}`, "none", connectors.flatMap((connector) => connectorShapes(connector, diagramBox)));
      layer.setAttribute(connectorLayerAttribute, "");
      layer.nativeConnectors = connectors.map((connector) => ({ ...connector, widthPx: connectorWidth }));
      diagram.appendChild(layer);
    });
  }

  function isIconHost(part, slide) {
    if (iconHostClasses.some((name) => part.classList.contains(name))) return true;
    const list = part.parentElement;
    return part.tagName === "LI" && Boolean(list) && ["OL", "UL"].includes(list.tagName) && list.parentElement === slide && iconListLayouts.includes(slide.getAttribute("data-layout"));
  }

  function iconFor(name) {
    const markup = (window.deckKitIcons || {})[name];
    const icon = element("span", markup ? "kit-icon" : "kit-icon kit-blank");
    if (!markup) return icon;
    icon.innerHTML = markup;
    icon.setAttribute(nativeIconAttribute, name);
    return icon;
  }

  function keyGroup(host) {
    const key = host.classList.contains("kit-keyed") ? host.querySelector(":scope > .kit-key") : null;
    if (!key) return host;
    const group = element("div", "kit-key-group");
    host.insertBefore(group, key);
    group.appendChild(key);
    return group;
  }

  function placeIcon(host, icon) {
    const parent = keyGroup(host);
    parent.insertBefore(icon, parent.firstChild);
    host.classList.add("kit-iconed");
  }

  function iconSiblings(host) {
    const name = iconHostClasses.find((className) => host.classList.contains(className));
    return name ? directChildren(host.parentElement, name) : listItems(host.parentElement);
  }

  function drawIcons() {
    slides().forEach((slide) => {
      const hosts = Array.from(slide.querySelectorAll(`[${iconAttribute}]`)).filter((part) => isIconHost(part, slide));
      const groups = new Set(hosts.flatMap(iconSiblings));
      groups.forEach((host) => {
        if (host.querySelector(".kit-icon")) return;
        placeIcon(host, iconFor((host.getAttribute(iconAttribute) || "").trim()));
      });
    });
  }

  function addListIndexes() {
    const lists = Array.from(document.querySelectorAll("section[data-layout] ol, section[data-layout='agenda'] > ul"));
    lists.forEach((list) => {
      Array.from(list.children).forEach((item, position) => {
        if (item.firstElementChild?.classList.contains("kit-index")) return;
        if (item.classList.contains("kit-iconed")) {
          groupPhrasing(item);
          return;
        }
        const index = element("span", "kit-index");
        index.textContent = String(position + 1).padStart(2, "0");
        item.insertBefore(index, item.firstChild);
        groupPhrasing(item);
      });
    });
  }

  function groupComparisonPoints() {
    document.querySelectorAll("section[data-layout='comparison'] > .column > ul > li").forEach(groupPhrasing);
  }

  function groupSteps() {
    document.querySelectorAll("section[data-layout='timeline']").forEach((slide) => {
      const steps = directChildren(slide, "step");
      if (!steps.length || directChildren(slide, "kit-steps").length) return;
      const group = element("div", "kit-steps");
      slide.insertBefore(group, steps[0]);
      steps.forEach((step) => group.appendChild(step));
    });
  }

  function addCoverRings() {
    document.querySelectorAll("section[data-layout='cover']").forEach((slide) => {
      if (slide.querySelector(":scope > img, :scope > .kit-ring")) return;
      coverRingRadii.forEach((radius) => slide.appendChild(element("span", "kit-ring", { width: `${radius}px`, height: `${radius}px` })));
    });
  }

  function addQuoteMarks() {
    document.querySelectorAll("section[data-layout='quote'] > blockquote").forEach((quote) => {
      if (quote.firstElementChild?.classList.contains("kit-quote-mark")) return;
      quote.insertBefore(element("span", "kit-quote-mark"), quote.firstChild);
      groupPhrasing(quote);
    });
  }

  function isPhrasing(node) {
    return node.nodeType === 3 || (node.nodeType === 1 && node.matches(phrasingSelector) && !isKitPart(node));
  }

  function groupPhrasing(container) {
    let run = [];
    const close = (before) => {
      if (run.some((node) => node.textContent.trim())) {
        const text = element("span", "kit-text");
        container.insertBefore(text, before);
        run.forEach((node) => text.appendChild(node));
      }
      run = [];
    };
    Array.from(container.childNodes).forEach((node) => {
      if (isPhrasing(node)) run.push(node);
      else close(node);
    });
    close(null);
  }

  function isMixedWord(word) {
    return hangulPattern.test(word) && Array.from(word).some((character) => !/\s/.test(character) && !hangulPattern.test(character));
  }

  function keptWord(...nodes) {
    const kept = element("span", "kit-keep");
    nodes.forEach((node) => kept.appendChild(node));
    return kept;
  }

  function textNodesIn(node, skipped = unkeptSelector) {
    if (node.nodeType === 3) return [node];
    if (node.nodeType !== 1 || (skipped && node.matches(skipped))) return [];
    return Array.from(node.childNodes).flatMap((child) => textNodesIn(child, skipped));
  }

  function inlineWordsIn(slide) {
    return Array.from(slide.querySelectorAll(keptInlineSelector)).filter((inline) => !inline.closest(unkeptSelector) && !isKitPart(inline) && !/\s/.test(inline.textContent.trim()));
  }

  function isKitPart(element) {
    return Array.from(element.classList).some((name) => name.startsWith("kit-"));
  }

  function isUnitOf(number, word) {
    return /\d/.test(number) && unitWordPattern.test(word);
  }

  function wordAfterInline(inline, text) {
    const attached = text.match(/^\S+/);
    if (attached) return isMixedWord(inline.textContent + attached[0]) ? attached[0] : null;
    const unit = text.match(/^\s+(\S+)/);
    return unit && isUnitOf(inline.textContent, unit[1]) ? unit[0] : null;
  }

  function keepWordAfterInline(inline) {
    const next = inline.nextSibling;
    if (!next || next.nodeType !== 3) return;
    const word = wordAfterInline(inline, next.textContent);
    if (!word || isWholeText(inline.parentElement, inline.textContent + word)) return;
    next.textContent = next.textContent.slice(word.length);
    const kept = element("span", "kit-keep");
    inline.replaceWith(kept);
    kept.append(inline, document.createTextNode(word));
  }

  function isWholeText(parent, text) {
    return parent.textContent.trim() === text.trim();
  }

  function textGroups(text) {
    const pieces = text.split(/(\s+)/).filter(Boolean);
    const groups = [];
    for (let index = 0; index < pieces.length; index += 1) {
      if (/\S/.test(pieces[index]) && index + 2 < pieces.length && isUnitOf(pieces[index], pieces[index + 2])) {
        groups.push({ text: pieces.slice(index, index + 3).join(""), kept: true });
        index += 2;
      } else {
        groups.push({ text: pieces[index], kept: isMixedWord(pieces[index]) });
      }
    }
    return groups;
  }

  function isBlockText(textNode, text) {
    return isWholeText(textNode.parentElement, text) && !textNode.parentElement.matches(phrasingSelector);
  }

  function keepWordsInText(textNode) {
    const groups = textGroups(textNode.textContent);
    if (!groups.some((group) => group.kept) || (groups.length === 1 && isBlockText(textNode, groups[0].text))) return;
    textNode.replaceWith(...groups.map((group) => (group.kept ? keptWord(document.createTextNode(group.text)) : document.createTextNode(group.text))));
  }

  function keepMixedWords() {
    slides().forEach((slide) => {
      inlineWordsIn(slide).forEach(keepWordAfterInline);
      textNodesIn(slide).forEach(keepWordsInText);
    });
  }

  function isTightlyTracked(element) {
    const style = getComputedStyle(element);
    const spacing = parseFloat(style.letterSpacing);
    const size = parseFloat(style.fontSize);
    return spacing / size < tightTrackingShare;
  }

  function trackHangulRun(textNode) {
    const pieces = textNode.textContent.split(hangulRunPattern).filter(Boolean);
    if (!pieces.some((piece) => hangulPattern.test(piece))) return;
    textNode.replaceWith(...pieces.map((piece) => {
      if (!hangulPattern.test(piece)) return document.createTextNode(piece);
      const run = element("span", "kit-hangul");
      run.textContent = piece;
      return run;
    }));
  }

  function trackHangul() {
    slides().forEach((slide) => {
      textNodesIn(slide, untrackedSelector).filter((node) => node.parentElement && !node.parentElement.classList.contains("kit-hangul") && isTightlyTracked(node.parentElement)).forEach(trackHangulRun);
    });
  }

  function isNumericColumn(cells) {
    const data = cells.filter((cell) => cell.tagName === "TD" && cell.textContent.trim());
    const numeric = data.filter((cell) => numericCellPattern.test(cell.textContent.trim()));
    return numeric.length > 0 && numeric.length * 2 >= data.length;
  }

  function markNumericCells() {
    document.querySelectorAll("section[data-layout] table").forEach((table) => {
      const rows = Array.from(table.querySelectorAll("tr"));
      const width = Math.max(0, ...rows.map((row) => row.children.length));
      for (let column = firstQuantityColumn; column < width; column += 1) {
        const cells = rows.map((row) => row.children[column]).filter(Boolean);
        if (isNumericColumn(cells)) cells.forEach((cell) => cell.classList.add("kit-number"));
      }
    });
  }

  function overflows(slide) {
    if (slide.scrollHeight > slide.clientHeight + overflowTolerance || slide.scrollWidth > slide.clientWidth + overflowTolerance) return true;
    if (partsCollide(slide)) return true;
    return Array.from(slide.querySelectorAll("*")).some((child) => {
      if (child.closest("aside.notes, .kit-chart") || child.clientHeight === 0) return false;
      return child.scrollHeight > child.clientHeight + overflowTolerance || child.scrollWidth > child.clientWidth + overflowTolerance;
    });
  }

  function placedParts(slide) {
    return Array.from(slide.children)
      .filter((child) => !child.classList.contains("kit-ring") && child.tagName !== "ASIDE")
      .map((child) => child.getBoundingClientRect())
      .filter((rect) => rect.width > 0 && rect.height > 0);
  }

  function rectanglesCollide(first, second) {
    const width = Math.min(first.right, second.right) - Math.max(first.left, second.left);
    const height = Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top);
    return width > overflowTolerance && height > overflowTolerance;
  }

  function partsCollide(slide) {
    const parts = placedParts(slide);
    return parts.some((part, index) => parts.slice(index + 1).some((other) => rectanglesCollide(part, other)));
  }

  function characterBox(node, offset) {
    const range = document.createRange();
    range.setStart(node, offset);
    range.setEnd(node, offset + 1);
    return range.getBoundingClientRect();
  }

  function characterTop(node, offset) {
    return characterBox(node, offset).top;
  }

  function spansLines(title) {
    const nodes = textNodesIn(title, null).filter((node) => node.textContent.trim());
    if (!nodes.length) return false;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    return characterTop(last, last.textContent.trimEnd().length - 1) > characterTop(first, first.textContent.search(/\S/)) + overflowTolerance;
  }

  function titleWords(title) {
    const words = [];
    let breakAt = null;
    textNodesIn(title, null).forEach((node) => {
      const isKept = Boolean(node.parentElement.closest(".kit-keep"));
      const text = node.textContent;
      for (let offset = 0; offset < text.length; offset += 1) {
        if (/\s/.test(text[offset])) {
          if (!isKept && !breakAt) breakAt = { node, offset };
          continue;
        }
        const box = characterBox(node, offset);
        const word = words[words.length - 1];
        if (word && !breakAt) Object.assign(word, { right: box.right, text: word.text + text[offset] });
        else words.push({ left: box.left, right: box.right, text: text[offset], breakAt });
        breakAt = null;
      }
    });
    return words;
  }

  function lineWidth(words, first, last) {
    return words[last].right - words[first].left;
  }

  function fewestLines(words, room) {
    let lines = 1;
    let first = 0;
    for (let index = 1; index < words.length; index += 1) {
      if (lineWidth(words, first, index) <= room) continue;
      lines += 1;
      first = index;
    }
    return lines;
  }

  function phraseBreaks(words, room) {
    const lines = fewestLines(words, room);
    const mean = lineWidth(words, 0, words.length - 1) / lines;
    const fits = (first, last) => lineWidth(words, first, last) <= room;
    const lineCost = (first, last) => (lineWidth(words, first, last) - mean) ** 2;
    const breakCost = (last) => (clauseEndPattern.test(words[last].text) ? 0 : (room * phraseBreakPenalty) ** 2);
    let best = words.map((_, last) => (fits(0, last) ? { cost: lineCost(0, last), starts: [] } : null));
    for (let line = 2; line <= lines; line += 1) {
      const previous = best;
      best = words.map((_, last) => {
        let chosen = null;
        for (let first = 1; first <= last; first += 1) {
          if (!previous[first - 1] || !fits(first, last)) continue;
          const cost = previous[first - 1].cost + lineCost(first, last) + breakCost(first - 1);
          if (!chosen || cost < chosen.cost) chosen = { cost, starts: [...previous[first - 1].starts, first] };
        }
        return chosen;
      });
    }
    return best[words.length - 1]?.starts || null;
  }

  function breakBefore(word) {
    const { node, offset } = word.breakAt;
    const rest = document.createTextNode(node.textContent.slice(offset).replace(/^\s+/, ""));
    node.textContent = node.textContent.slice(0, offset);
    node.parentNode.insertBefore(rest, node.nextSibling);
    node.parentNode.insertBefore(element("br", "kit-break"), rest);
  }

  async function breakAtPhrases(title, slide, layOut) {
    const before = title.getBoundingClientRect();
    title.style.setProperty("white-space", "nowrap");
    if (layOut) await layOut(slide);
    const words = titleWords(title);
    title.style.removeProperty("white-space");
    const starts = words.length > 1 ? phraseBreaks(words, before.width) : null;
    if (starts) starts.slice().reverse().forEach((start) => breakBefore(words[start]));
    if (layOut) await layOut(slide);
    return Boolean(starts) && Math.abs(title.getBoundingClientRect().height - before.height) <= overflowTolerance && title.scrollWidth <= title.clientWidth + overflowTolerance;
  }

  async function balanceTitle(title, slide, layOut) {
    if (title.querySelector("br") || !spansLines(title)) return;
    const original = Array.from(title.childNodes).map((node) => node.cloneNode(true));
    if (await breakAtPhrases(title, slide, layOut)) return;
    Array.from(title.childNodes).forEach((node) => node.remove());
    original.forEach((node) => title.appendChild(node));
    await narrowTitle(title, slide, layOut);
  }

  async function narrowTitle(title, slide, layOut) {
    const height = title.getBoundingClientRect().height;
    let fits = title.getBoundingClientRect().width;
    let wraps = fits / 2;
    for (let step = 0; step < balanceSteps; step += 1) {
      const width = (fits + wraps) / 2;
      title.style.setProperty("max-width", `${width}px`);
      if (layOut) await layOut(slide);
      if (title.getBoundingClientRect().height > height + overflowTolerance) wraps = width;
      else fits = width;
    }
    title.style.setProperty("max-width", `${Math.ceil(fits)}px`);
    if (layOut) await layOut(slide);
  }

  async function balanceTitles(slide, layOut) {
    for (const title of Array.from(slide.children).filter((child) => ["H1", "H2"].includes(child.tagName))) await balanceTitle(title, slide, layOut);
  }

  function lineCountOf(element) {
    const tops = textNodesIn(element, null).flatMap((node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      return Array.from(range.getClientRects()).map((rect) => (rect.top + rect.bottom) / 2);
    });
    const lines = [];
    tops.sort((first, second) => first - second).forEach((center) => {
      if (!lines.length || center - lines[lines.length - 1] > overflowTolerance * 4) lines.push(center);
    });
    return lines.length;
  }

  function titlesRunLong(slide) {
    return Array.from(slide.children).some((child) => ["H1", "H2"].includes(child.tagName) && lineCountOf(child) > titleLineMaximum);
  }

  function fits(slide) {
    return !slide.clientHeight || (!overflows(slide) && !titlesRunLong(slide));
  }

  function canGrow(slide) {
    return growingLayouts.has(slide.getAttribute("data-layout")) || slide.classList.contains("kit-carded");
  }

  function rowItems(slide) {
    return Array.from(slide.children).filter((child) => rowItemClasses.some((className) => child.classList.contains(className)));
  }

  function rowsOf(items) {
    const rows = new Map();
    items.forEach((item) => {
      const top = Math.round(item.getBoundingClientRect().top);
      rows.set(top, [...(rows.get(top) || []), item]);
    });
    return Array.from(rows.values()).filter((row) => row.length > 1);
  }

  function partRole(part, isLast) {
    if (part.classList.contains("value")) return "value";
    if (part.classList.contains("label")) return "label";
    if (part.tagName === "H3") return "heading";
    return isLast ? "closing" : "text";
  }

  function rolesOf(item) {
    const parts = Array.from(item.children).filter((part) => part.getBoundingClientRect().height > 0);
    const seen = {};
    return parts.map((part, index) => {
      const role = partRole(part, index === parts.length - 1 && index > 0);
      seen[role] = (seen[role] || 0) + 1;
      return { part, key: `${role}${seen[role]}` };
    });
  }

  function alignRow(row) {
    const parts = row.flatMap(rolesOf);
    const keys = new Set(parts.map((entry) => entry.key));
    keys.forEach((key) => {
      const shared = parts.filter((entry) => entry.key === key);
      if (shared.length < 2) return;
      const tallest = Math.max(...shared.map((entry) => entry.part.getBoundingClientRect().height));
      shared.forEach((entry) => {
        entry.part.setAttribute(alignedAttribute, "");
        entry.part.style.setProperty("min-height", `${Math.ceil(tallest)}px`);
      });
    });
  }

  function clearRowAlignment(slide) {
    slide.querySelectorAll(`[${alignedAttribute}]`).forEach((part) => {
      part.removeAttribute(alignedAttribute);
      part.style.removeProperty("min-height");
    });
  }

  async function settle(slide, layOut) {
    clearRowAlignment(slide);
    if (layOut) await layOut(slide);
    const rows = rowsOf(rowItems(slide));
    if (!rows.length) return;
    rows.forEach(alignRow);
    if (layOut) await layOut(slide);
  }

  function clearItemBounds(slide) {
    slide.querySelectorAll(`[${boundedAttribute}]`).forEach((item) => {
      item.removeAttribute(boundedAttribute);
      ["height", "align-self"].forEach((name) => item.style.removeProperty(name));
    });
  }

  function boundedAlignment(item) {
    if (!item.parentElement.classList.contains("kit-grid")) return "center";
    return item.classList.contains("kit-second-row") ? "start" : "end";
  }

  async function boundItemSlack(slide, layOut) {
    clearItemBounds(slide);
    const items = rowItems(slide);
    if (!items.length) return;
    const stretched = Math.max(...items.map((item) => boxSize(item).height));
    items.forEach((item) => item.style.setProperty("align-self", "start"));
    if (layOut) await layOut(slide);
    const allowed = Math.ceil(Math.max(...items.map((item) => boxSize(item).height)) * (1 + itemSlackShare));
    items.forEach((item) => item.style.removeProperty("align-self"));
    if (stretched <= allowed) {
      if (layOut) await layOut(slide);
      return;
    }
    items.forEach((item) => {
      item.setAttribute(boundedAttribute, "");
      item.style.setProperty("height", `${allowed}px`);
      item.style.setProperty("align-self", boundedAlignment(item));
    });
    if (layOut) await layOut(slide);
  }

  async function growSlide(slide, layOut) {
    if (!canGrow(slide)) return false;
    for (const step of growSteps) {
      slide.style.setProperty("--grow", String(step));
      await settle(slide, layOut);
      if (fits(slide)) return true;
    }
    slide.style.removeProperty("--grow");
    slide.classList.add("kit-full");
    return false;
  }

  async function fitSlide(slide, layOut) {
    slide.removeAttribute(capacityAttribute);
    if (await growSlide(slide, layOut)) return;
    for (const step of fitSteps) {
      slide.style.setProperty("--fit", String(step));
      await settle(slide, layOut);
      if (fits(slide)) return;
      if (step === fitSteps[0]) slide.setAttribute(capacityAttribute, JSON.stringify(slideCapacity(slide)));
    }
  }

  function contentFloor(slide) {
    const footer = directChildren(slide, "kit-footer")[0];
    return slide.getBoundingClientRect().bottom - (footer ? footer.getBoundingClientRect().height : 0);
  }

  function partName(element) {
    const named = capacityPartNames.find(([selector]) => element.matches(selector));
    return named ? named[1] : element.tagName.toLowerCase();
  }

  function partIndex(element) {
    const siblings = Array.from(element.parentElement.children).filter((sibling) => partName(sibling) === partName(element));
    return siblings.indexOf(element) + 1;
  }

  function itemsOf(part) {
    if (part.tagName === "TABLE") return Array.from(part.querySelectorAll("tr")).filter((row) => row.querySelector("td"));
    if (["OL", "UL"].includes(part.tagName)) return Array.from(part.children);
    if (part.classList.contains("kit-steps")) return Array.from(part.children);
    return [];
  }

  function spills(element, floor) {
    const rect = element.getBoundingClientRect();
    return element.scrollHeight > element.clientHeight + overflowTolerance || rect.bottom > floor + overflowTolerance;
  }

  function textShare(element, floor) {
    const rect = element.getBoundingClientRect();
    const room = Math.min(element.clientHeight || rect.height, floor - rect.top);
    return Math.max(0, Math.min(1, room / Math.max(element.scrollHeight, rect.height, 1)));
  }

  function textCapacity(element, floor) {
    const characters = element.textContent.replace(/\s+/g, " ").trim().length;
    return { part: partName(element), index: partIndex(element), characters, fits: Math.floor(characters * textShare(element, floor)) };
  }

  function partCapacity(part, floor) {
    const items = itemsOf(part);
    const limit = Math.min(floor, part.getBoundingClientRect().bottom) + overflowTolerance;
    const shown = items.filter((item) => item.getBoundingClientRect().bottom <= limit).length;
    if (items.length && shown < items.length) return { part: partName(part), index: partIndex(part), items: items.length, fits: shown };
    const crowded = items.find((item) => spills(item, floor));
    return textCapacity(crowded || part, floor);
  }

  function slideCapacity(slide) {
    const floor = contentFloor(slide);
    const parts = Array.from(slide.children).filter((child) => !child.matches("aside, .kit-footer, .kit-ring") && child.getBoundingClientRect().height > 0);
    const crowded = parts.filter((part) => spills(part, floor) || itemsOf(part).some((item) => spills(item, floor)));
    if (crowded.length) return crowded.map((part) => partCapacity(part, floor));
    const used = Math.max(...parts.map((part) => part.getBoundingClientRect().bottom)) - slide.getBoundingClientRect().top;
    return [{ part: "slide", index: 1, share: Math.round(((floor - slide.getBoundingClientRect().top) / Math.max(used, 1)) * 100) / 100 }];
  }

  function parseList(text) {
    const separator = /,\s/.test(text || "") ? /,\s+/ : /,/;
    return (text || "").split(separator).map((value) => value.trim()).filter((value) => value !== "");
  }

  function parseNumber(text) {
    const compact = String(text).replace(/\s/g, "").replace("−", "-");
    return Number(groupedNumberPattern.test(compact) ? compact.replace(/,/g, "") : compact);
  }

  function chartData(figure) {
    const labels = parseList(figure.getAttribute("data-labels"));
    const seriesText = figure.getAttribute("data-series");
    if (seriesText) {
      const series = seriesText.split(";").map((part) => part.trim()).filter(Boolean).map((part) => {
        const separator = part.indexOf(":");
        return { name: part.slice(0, separator).trim(), values: parseList(part.slice(separator + 1)).map(parseNumber) };
      });
      return { labels, series };
    }
    return { labels, series: [{ name: figure.getAttribute("data-name") || "", values: parseList(figure.getAttribute("data-values")).map(parseNumber) }] };
  }

  function decimalsOf(series) {
    return Math.min(2, Math.max(0, ...series.flatMap((item) => item.values).map((value) => (String(value).split(".")[1] || "").length)));
  }

  function axisOf(type, seriesIndex, seriesCount) {
    if (type === "combo") return seriesIndex === seriesCount - 1 ? 1 : 0;
    if (type === "scatter") return seriesIndex;
    return 0;
  }

  function axisUnits(figure, type) {
    const text = figure.getAttribute("data-unit") || "";
    if (!twoAxisTypes.has(type)) return [text, text];
    const units = text.split(",").map((unit) => unit.trim());
    return [units[0], units.length > 1 ? units[1] : units[0]];
  }

  function seriesFormats(figure, type, series) {
    const units = axisUnits(figure, type);
    const axes = series.map((_, index) => axisOf(type, index, series.length));
    const decimals = [0, 1].map((axis) => decimalsOf(series.filter((_, index) => axes[index] === axis)));
    return axes.map((axis) => {
      const formatter = new Intl.NumberFormat(locale(), { maximumFractionDigits: decimals[axis], minimumFractionDigits: decimals[axis] });
      return { unit: units[axis], decimals: decimals[axis], format: (value) => formatter.format(value) + units[axis] };
    });
  }

  function seriesColors(count) {
    const palette = ["var(--accent)", "var(--accent-2)", "var(--chart-muted)", "var(--muted)", "color-mix(in srgb, var(--accent) 45%, var(--bg))", "color-mix(in srgb, var(--accent-2) 45%, var(--bg))", "var(--ink-soft)", "var(--line)"];
    return Array.from({ length: count }, (_, index) => palette[index % palette.length]);
  }

  function legendFor(series, colors) {
    const legend = element("div", "kit-legend");
    series.forEach((item, index) => {
      const entry = element("span");
      entry.append(element("i", "kit-swatch", { background: colors[index] }), document.createTextNode(item.name));
      legend.appendChild(entry);
    });
    return legend;
  }

  function scaledRange(minimum, maximum) {
    if (maximum === minimum) maximum = minimum + 1;
    return { minimum, maximum, share: (value) => (value - minimum) / (maximum - minimum) };
  }

  function niceRange(values, includeZero) {
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    if (includeZero) return scaledRange(Math.min(0, minimum), Math.max(0, maximum));
    const padding = (maximum - minimum || Math.abs(maximum) || 1) * 0.25;
    return scaledRange(minimum - padding, maximum + padding * 0.6);
  }

  function bandRange(values, lowShare, highShare) {
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const span = maximum - minimum || Math.abs(maximum) || 1;
    const whole = span / (highShare - lowShare);
    const bottom = minimum - (maximum === minimum ? span / 2 : 0) - whole * lowShare;
    return scaledRange(bottom, bottom + whole);
  }

  function resolvedChannels(host, color) {
    const probe = element("i", "", { color });
    host.appendChild(probe);
    const channels = (getComputedStyle(probe).color.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    probe.remove();
    return channels.length === 3 ? channels : null;
  }

  function relativeLuminance(channels) {
    const linear = channels.map((channel) => {
      const share = channel / 255;
      return share <= 0.03928 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  }

  function contrastRatio(first, second) {
    const [lighter, darker] = [relativeLuminance(first), relativeLuminance(second)].sort((one, other) => other - one);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function insideLabelInk(host, fill) {
    const background = resolvedChannels(host, fill);
    if (!background) return insideLabelInks[0];
    const ranked = insideLabelInks
      .map((ink) => ({ ink, channels: resolvedChannels(host, ink) }))
      .filter(({ channels }) => channels)
      .sort((first, second) => contrastRatio(second.channels, background) - contrastRatio(first.channels, background));
    return ranked.length ? ranked[0].ink : insideLabelInks[0];
  }

  function highlighted(figure) {
    return figure.getAttribute("data-highlight");
  }

  function isMuted(figure, data, label) {
    return data.series.length === 1 && Boolean(highlighted(figure)) && label !== highlighted(figure);
  }

  function barColor(figure, data, seriesIndex, label, colors) {
    if (isMuted(figure, data, label)) return "var(--chart-muted)";
    return colors[seriesIndex];
  }

  function valueLabel(text, className, position, point) {
    const label = element("span", `kit-data-label ${className}`.trim(), position);
    label.textContent = text;
    if (point) {
      label.setAttribute("data-series", String(point.series));
      label.setAttribute("data-point", String(point.index));
      if (point.position) label.setAttribute("data-position", point.position);
    }
    return label;
  }

  function barsPerGroup(seriesCount, stacks) {
    return stacks ? 1 : seriesCount;
  }

  function bandFill(barCount) {
    return barCount > 1 ? clusterBandFill : barBandFill;
  }

  function barShareOfSlot(barCount) {
    return barCount > 1 ? 1 - clusterGapShare : 1;
  }

  function lineStartsAtZero(figure) {
    return figure.getAttribute("data-zero") === "true";
  }

  function categoryAxis(chart, className) {
    const area = element("div", `kit-plot-area ${className}`.trim());
    const categories = element("div", `kit-categories ${className ? "kit-line-categories" : ""}`.trim());
    chart.append(area, categories);
    return { area, categories };
  }

  function addCategory(categories, label, left) {
    const categoryLabel = element("span", "kit-category", { left: percent(left) });
    categoryLabel.textContent = label;
    categories.appendChild(categoryLabel);
    return categoryLabel;
  }

  function columnRange(data, mode, totals) {
    if (mode === "percent") return scaledRange(0, 100);
    if (mode === "stacked") return niceRange(totals, true);
    const range = niceRange(data.series.flatMap((item) => item.values), true);
    return mode === "combo" ? scaledRange(range.minimum, range.maximum / comboColumnShare) : range;
  }

  function renderColumns(figure, data, chart, formats, mode) {
    const { area, categories } = categoryAxis(chart, "");
    const colors = seriesColors(data.series.length);
    const stacks = mode === "stacked" || mode === "percent";
    const totals = data.labels.map((_, category) => data.series.reduce((sum, item) => sum + Math.max(0, item.values[category]), 0));
    const range = columnRange(data, mode, totals);
    const top = (value) => (1 - range.share(value)) * 100;
    const zero = top(0);
    const slot = 100 / data.labels.length;
    const bars = barsPerGroup(data.series.length, stacks);
    const group = slot * bandFill(bars);
    const barWidth = group / bars;
    const drawnShare = barShareOfSlot(bars);
    const labels = [];
    data.labels.forEach((label, category) => {
      const center = slot * category + slot / 2;
      const left = center - group / 2;
      if (stacks) {
        let stackTop = zero;
        data.series.forEach((item, seriesIndex) => {
          const value = Math.max(0, item.values[category]);
          const height = zero - top(mode === "percent" ? (value / (totals[category] || 1)) * 100 : value);
          stackTop -= height;
          area.appendChild(element("div", "kit-segment", { left: percent(left), top: percent(stackTop), width: percent(barWidth), height: percent(height), background: colors[seriesIndex] }));
          if (height >= 7 && seriesIndex < insideLabelSeries) {
            labels.push(valueLabel(formats[seriesIndex].format(value), "kit-inside", { left: percent(center), top: percent(stackTop + height / 2), color: insideLabelInk(figure, colors[seriesIndex]) }, { series: seriesIndex, index: category }));
          }
        });
        if (mode === "stacked") labels.push(valueLabel(formats[0].format(totals[category]), "", { left: percent(center), top: percent(stackTop) }));
      } else {
        data.series.forEach((item, seriesIndex) => {
          const value = item.values[category];
          const barLeft = left + seriesIndex * barWidth;
          const barTop = Math.min(top(value), zero);
          const height = Math.max(0.3, Math.abs(zero - top(value)));
          const negative = value < 0 ? " kit-negative" : "";
          area.appendChild(element("div", `kit-bar${negative}`, { left: percent(barLeft + (barWidth * (1 - drawnShare)) / 2), top: percent(barTop), width: percent(barWidth * drawnShare), height: percent(height), background: barColor(figure, data, seriesIndex, label, colors) }));
          const muted = isMuted(figure, data, label) ? " kit-muted" : "";
          labels.push(valueLabel(formats[seriesIndex].format(value), `${value < 0 ? "kit-below" : ""}${muted}`, { left: percent(barLeft + barWidth / 2), top: percent(value < 0 ? barTop + height : barTop) }, { series: seriesIndex, index: category }));
        });
      }
      addCategory(categories, label, center);
    });
    area.appendChild(element("div", "kit-baseline", { top: percent(zero) }));
    labels.forEach((label) => area.appendChild(label));
    return { area, xOf: (index) => slot * index + slot / 2, range };
  }

  function renderBars(figure, data, chart, formats) {
    const rows = element("div", "kit-bar-rows");
    chart.appendChild(rows);
    const colors = seriesColors(data.series.length);
    const range = niceRange(data.series.flatMap((item) => item.values), true);
    const slot = 100 / data.labels.length;
    const bars = barsPerGroup(data.series.length, false);
    const group = slot * bandFill(bars);
    const barHeight = group / bars;
    const drawnShare = barShareOfSlot(bars);
    const position = (value) => range.share(value) * 100 * barScaleShare;
    const zero = position(0);
    const labels = element("div", "kit-bar-labels");
    const area = element("div", "kit-bar-area");
    rows.append(labels, area);
    data.labels.forEach((label, category) => {
      const center = slot * category + slot / 2;
      const categoryLabel = element("span", "kit-category kit-row", { top: percent(center) });
      categoryLabel.textContent = label;
      labels.appendChild(categoryLabel);
      data.series.forEach((item, seriesIndex) => {
        const value = item.values[category];
        const barTop = center - group / 2 + seriesIndex * barHeight;
        const left = Math.min(position(value), zero);
        const width = Math.max(0.3, Math.abs(position(value) - zero));
        const negative = value < 0 ? " kit-negative" : "";
        area.appendChild(element("div", `kit-bar kit-horizontal${negative}`, { left: percent(left), top: percent(barTop + (barHeight * (1 - drawnShare)) / 2), width: percent(width), height: percent(barHeight * drawnShare), background: barColor(figure, data, seriesIndex, label, colors) }));
        const muted = isMuted(figure, data, label) ? " kit-muted" : "";
        area.appendChild(valueLabel(formats[seriesIndex].format(value), `${value < 0 ? "kit-start" : "kit-end"}${muted}`, { left: percent(value < 0 ? left : left + width), top: percent(barTop + barHeight / 2) }, { series: seriesIndex, index: category }));
      });
    });
    area.appendChild(element("div", "kit-baseline kit-vertical", { left: percent(zero) }));
  }

  function lineX(count) {
    return (index) => (count === 1 ? 50 : lineInsetShare + (index * (100 - 2 * lineInsetShare)) / (count - 1));
  }

  function polylineLayer(color, points, filled) {
    const outline = points.map((point) => point.join(",")).join(" ");
    const shapes = [svgElement("polyline", { points: outline, fill: "none", stroke: "currentColor", "stroke-width": 5, "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" })];
    if (filled) shapes.unshift(svgElement("path", { d: `M${points[0][0]},1000 L${outline.split(" ").join(" L")} L${points[points.length - 1][0]},1000 Z`, fill: "currentColor", "fill-opacity": 0.1 }));
    return svgLayer(color, "0 0 1000 1000", "none", shapes);
  }

  function addDots(area, values, color, position) {
    values.forEach((value, index) => {
      const isLast = index === values.length - 1;
      const point = position(index, value);
      area.appendChild(element("i", `kit-dot${isLast ? " kit-last" : ""}`, { left: percent(point.x), top: percent(point.y), "border-color": color, background: isLast ? color : "var(--bg)" }));
    });
  }

  function lineLabels(values, seriesIndex, format, position, labelEveryPoint, isBelow) {
    return values.flatMap((value, index) => {
      const isLast = index === values.length - 1;
      if (!labelEveryPoint && !isLast) return [];
      const point = position(index, value);
      const below = isBelow(index, value);
      return [valueLabel(format(value), `${below ? "kit-below" : ""}${isLast ? "" : " kit-muted"}`, { left: percent(point.x), top: percent(point.y) }, { series: seriesIndex, index, position: below ? "b" : "t" })];
    });
  }

  function renderLine(figure, data, chart, formats) {
    const { area, categories } = categoryAxis(chart, "kit-line-area");
    const colors = seriesColors(data.series.length);
    const range = niceRange(data.series.flatMap((item) => item.values), lineStartsAtZero(figure));
    const xOf = lineX(data.labels.length);
    const position = (index, value) => ({ x: xOf(index), y: (1 - range.share(value)) * 100 });
    [0, 50, 100].forEach((share) => area.appendChild(element("div", "kit-gridline", { top: percent(share) })));
    const labelEveryPoint = data.series.length <= 2 && data.labels.length <= 8;
    data.series.forEach((item, seriesIndex) => {
      const points = item.values.map((value, index) => [position(index, value).x * 10, position(index, value).y * 10]);
      area.appendChild(polylineLayer(colors[seriesIndex], points, data.series.length === 1));
    });
    data.series.forEach((item, seriesIndex) => addDots(area, item.values, colors[seriesIndex], position));
    const isBelow = (seriesIndex) => (index, value) => data.series.length === 2 && seriesIndex === 1 && value < data.series[0].values[index];
    data.series.flatMap((item, seriesIndex) => lineLabels(item.values, seriesIndex, formats[seriesIndex].format, position, labelEveryPoint, isBelow(seriesIndex))).forEach((label) => area.appendChild(label));
    data.labels.forEach((label, index) => addCategory(categories, label, xOf(index)));
    area.appendChild(element("div", "kit-baseline kit-faint", { top: "100%" }));
  }

  function renderArea(figure, data, chart, formats) {
    const { area, categories } = categoryAxis(chart, "kit-line-area");
    const colors = seriesColors(data.series.length);
    const totals = data.labels.map((_, index) => data.series.reduce((sum, item) => sum + Math.max(0, item.values[index]), 0));
    const range = niceRange(totals, true);
    const xOf = lineX(data.labels.length);
    const yOf = (value) => (1 - range.share(value)) * 100;
    [0, 50, 100].forEach((share) => area.appendChild(element("div", "kit-gridline", { top: percent(share) })));
    let floor = data.labels.map(() => 0);
    const labels = [];
    data.series.forEach((item, seriesIndex) => {
      const ceiling = floor.map((below, index) => below + Math.max(0, item.values[index]));
      const upper = ceiling.map((value, index) => `${xOf(index) * 10},${yOf(value) * 10}`);
      const lower = floor.map((value, index) => `${xOf(index) * 10},${yOf(value) * 10}`).reverse();
      area.appendChild(svgLayer(colors[seriesIndex], "0 0 1000 1000", "none", [svgElement("path", { d: `M${upper.join(" L")} L${lower.join(" L")} Z`, fill: "currentColor" })]));
      const last = data.labels.length - 1;
      const height = yOf(floor[last]) - yOf(ceiling[last]);
      if (height >= 7 && seriesIndex < insideLabelSeries) {
        labels.push(valueLabel(formats[seriesIndex].format(item.values[last]), "kit-inside kit-before", { left: percent(xOf(last)), top: percent(yOf(ceiling[last]) + height / 2), color: insideLabelInk(figure, colors[seriesIndex]) }, { series: seriesIndex, index: last }));
      }
      floor = ceiling;
    });
    labels.forEach((label) => area.appendChild(label));
    data.labels.forEach((label, index) => addCategory(categories, label, xOf(index)));
    area.appendChild(element("div", "kit-baseline kit-faint", { top: "100%" }));
  }

  function renderCombo(figure, data, chart, formats) {
    const columns = { labels: data.labels, series: data.series.slice(0, -1) };
    const line = data.series[data.series.length - 1];
    const lineIndex = data.series.length - 1;
    const color = seriesColors(data.series.length)[lineIndex];
    const { area, xOf, range: columnScale } = renderColumns(figure, columns, chart, formats, "combo");
    const range = bandRange(line.values, comboLineBand[0], comboLineBand[1]);
    const position = (index, value) => ({ x: xOf(index), y: (1 - range.share(value)) * 100 });
    const points = line.values.map((value, index) => [position(index, value).x * 10, position(index, value).y * 10]);
    area.appendChild(polylineLayer(color, points, false));
    addDots(area, line.values, color, position);
    lineLabels(line.values, lineIndex, formats[lineIndex].format, position, data.labels.length <= 8, () => false).forEach((label) => area.appendChild(label));
    chart.primaryRange = columnScale;
    chart.secondaryRange = range;
  }

  function roundStep(span) {
    const magnitude = 10 ** Math.floor(Math.log10(span));
    const multiple = roundStepMultiples.find((candidate) => span / magnitude <= candidate);
    return multiple * magnitude;
  }

  function tickedRange(values) {
    const padded = niceRange(values, false);
    const step = roundStep((padded.maximum - padded.minimum) / tickIntervals);
    const range = scaledRange(Math.floor(padded.minimum / step) * step, Math.ceil(padded.maximum / step) * step);
    return { ...range, step };
  }

  function stepDecimals(step) {
    return Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
  }

  function axisTicks(range, unit) {
    const decimals = stepDecimals(range.step);
    const formatter = new Intl.NumberFormat(locale(), { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
    const count = Math.round((range.maximum - range.minimum) / range.step);
    return Array.from({ length: count + 1 }, (_, index) => {
      const value = range.minimum + index * range.step;
      return { share: Math.round(range.share(value) * 1000) / 10, text: formatter.format(value) + unit };
    });
  }

  function scatterColor(figure, label) {
    const highlight = highlighted(figure);
    return !highlight || label === highlight ? "var(--accent)" : "var(--chart-muted)";
  }

  function renderScatter(figure, data, chart, formats) {
    chart.classList.add("kit-scatter");
    const [horizontal, vertical] = data.series;
    const xRange = tickedRange(horizontal.values);
    const yRange = tickedRange(vertical.values);
    const verticalTitle = element("span", "kit-axis-title");
    verticalTitle.textContent = vertical.name;
    const { area, categories } = categoryAxis(chart, "kit-scatter-area");
    chart.insertBefore(verticalTitle, area);
    const horizontalTitle = element("span", "kit-axis-title kit-axis-x");
    horizontalTitle.textContent = horizontal.name;
    chart.appendChild(horizontalTitle);
    axisTicks(yRange, formats[1].unit).forEach(({ share, text }) => {
      area.appendChild(element("div", "kit-gridline", { top: percent(100 - share) }));
      const tick = element("span", `kit-tick ${edgeTickClasses[100 - share] || ""}`.trim(), { top: percent(100 - share) });
      tick.textContent = text;
      area.appendChild(tick);
    });
    axisTicks(xRange, formats[0].unit).forEach(({ share, text }) => {
      area.appendChild(element("div", "kit-gridline kit-vertical", { left: percent(share) }));
      addCategory(categories, text, share).classList.add(edgeTickClasses[share] || "kit-middle");
    });
    const position = (index) => ({ x: xRange.share(horizontal.values[index]) * 100, y: (1 - yRange.share(vertical.values[index])) * 100 });
    data.labels.forEach((label, index) => {
      const point = position(index);
      const color = scatterColor(figure, label);
      area.appendChild(element("i", "kit-dot kit-last", { left: percent(point.x), top: percent(point.y), "border-color": color, background: color }));
    });
    data.labels.forEach((label, index) => {
      const point = position(index);
      const onLeft = point.x > scatterLabelSwitchShare;
      const muted = scatterColor(figure, label) === "var(--chart-muted)" ? " kit-muted" : "";
      area.appendChild(valueLabel(label, `${onLeft ? "kit-start" : "kit-end"} kit-point-name${muted}`, { left: percent(point.x), top: percent(point.y) }, { series: 0, index, position: onLeft ? "l" : "r" }));
    });
    chart.primaryRange = xRange;
    chart.secondaryRange = yRange;
  }

  function donutCenter(figure, data) {
    const values = data.series[0].values;
    const total = values.reduce((sum, value) => sum + value, 0);
    return figure.getAttribute("data-center") || `${Math.round((values[0] / total) * 100)}%`;
  }

  function donutCenterLabel(figure, data) {
    return figure.getAttribute("data-center-label") || data.labels[0];
  }

  function renderDonut(figure, data, chart, formats, isPie) {
    chart.classList.add("kit-donut");
    const values = data.series[0].values;
    const total = values.reduce((sum, value) => sum + value, 0);
    const colors = seriesColors(values.length);
    const ring = element("div", "kit-donut-ring");
    const radius = isPie ? 50 : 80;
    const strokeWidth = isPie ? 100 : 40;
    const circumference = 2 * Math.PI * radius;
    let offset = 0;
    values.forEach((value, index) => {
      const length = (value / total) * circumference;
      const gap = values.length > 1 ? 1.5 : 0;
      const slice = svgElement("circle", { cx: 100, cy: 100, r: radius, fill: "none", stroke: "currentColor", "stroke-width": strokeWidth, "stroke-dasharray": `${Math.max(0, length - gap)} ${circumference}`, "stroke-dashoffset": -offset, transform: "rotate(-90 100 100)" });
      ring.appendChild(svgLayer(colors[index], "0 0 200 200", "xMidYMid meet", [slice]));
      offset += length;
    });
    if (!isPie) {
      const center = element("div", "kit-donut-center");
      const big = element("b");
      big.textContent = donutCenter(figure, data);
      const caption = element("span");
      caption.textContent = donutCenterLabel(figure, data);
      center.append(big, caption);
      ring.appendChild(center);
    }
    const legend = element("div", "kit-donut-legend");
    const valuesAreShares = formats[0].unit.trim() === "%";
    data.labels.forEach((label, index) => {
      const row = element("div");
      const name = element("span");
      name.textContent = label;
      const amount = element("b");
      amount.textContent = formats[0].format(values[index]);
      row.append(element("i", "kit-swatch"), name, amount);
      if (!valuesAreShares) {
        const share = element("span", "kit-share");
        share.textContent = `${Math.round((values[index] / total) * 100)}%`;
        row.appendChild(share);
      }
      row.firstChild.style.setProperty("background", colors[index]);
      legend.appendChild(row);
    });
    chart.append(ring, legend);
  }

  const chartRenderers = {
    column: (figure, data, chart, formats) => renderColumns(figure, data, chart, formats, "clustered"),
    stacked: (figure, data, chart, formats) => renderColumns(figure, data, chart, formats, "stacked"),
    stacked100: (figure, data, chart, formats) => renderColumns(figure, data, chart, formats, "percent"),
    bar: (figure, data, chart, formats) => renderBars(figure, data, chart, formats),
    line: (figure, data, chart, formats) => renderLine(figure, data, chart, formats),
    area: (figure, data, chart, formats) => renderArea(figure, data, chart, formats),
    combo: (figure, data, chart, formats) => renderCombo(figure, data, chart, formats),
    scatter: (figure, data, chart, formats) => renderScatter(figure, data, chart, formats),
    donut: (figure, data, chart, formats) => renderDonut(figure, data, chart, formats, false),
    pie: (figure, data, chart, formats) => renderDonut(figure, data, chart, formats, true),
  };

  function legendSeries(type, data) {
    if (type === "scatter") return [];
    return data.series.length > 1 ? data.series : [];
  }

  function renderChart(figure) {
    Array.from(figure.children).filter((child) => child.classList.contains("kit-chart")).forEach((previous) => previous.remove());
    const type = figure.getAttribute("data-chart");
    const renderer = chartRenderers[type];
    if (!renderer) return;
    const data = chartData(figure);
    const chart = element("div", `kit-chart kit-chart-${type}`);
    figure.insertBefore(chart, figure.firstChild);
    const legend = legendSeries(type, data);
    if (legend.length) chart.appendChild(legendFor(legend, seriesColors(legend.length)));
    const formats = seriesFormats(figure, type, data.series);
    renderer(figure, data, chart, formats);
    chart.setAttribute("data-native-chart", "");
    chart.nativeChart = nativeChart(figure, type, data, formats, chart);
  }

  function rangeLimits(range) {
    return range ? { minimum: range.minimum, maximum: range.maximum } : null;
  }

  function nativeBars(type, data) {
    const stacks = type === "stacked" || type === "stacked100";
    return barsPerGroup(type === "combo" ? data.series.length - 1 : data.series.length, stacks);
  }

  function gapWidth(type, data) {
    const bars = nativeBars(type, data);
    const share = bandFill(bars);
    return Math.round(((1 - share) / share) * (bars / barShareOfSlot(bars)) * 100);
  }

  function barOverlap(type, data) {
    const drawnShare = barShareOfSlot(nativeBars(type, data));
    return drawnShare < 1 ? -Math.round(((1 - drawnShare) / drawnShare) * 100) : 0;
  }

  function pointColors(figure, type, data) {
    if (type === "donut" || type === "pie") return [seriesColors(data.labels.length)];
    if (type === "scatter") return [data.labels.map((label) => scatterColor(figure, label))];
    const colors = seriesColors(data.series.length);
    const usesHighlight = type === "column" || type === "bar";
    return data.series.map((_, seriesIndex) => data.labels.map((label) => (usesHighlight ? barColor(figure, data, seriesIndex, label, colors) : colors[seriesIndex])));
  }

  function valueRange(figure, type, data, chart) {
    if (type === "line") return niceRange(data.series.flatMap((item) => item.values), lineStartsAtZero(figure));
    if (type === "area") return niceRange(data.labels.map((_, index) => data.series.reduce((sum, item) => sum + Math.max(0, item.values[index]), 0)), true);
    return chart.primaryRange || null;
  }

  function nativeChart(figure, type, data, formats, chart) {
    return {
      type,
      labels: data.labels,
      series: data.series,
      units: formats.map((format) => format.unit),
      decimals: formats.map((format) => format.decimals),
      startsAtZero: type !== "line" || lineStartsAtZero(figure),
      valueRange: rangeLimits(valueRange(figure, type, data, chart)),
      secondaryRange: rangeLimits(chart.secondaryRange),
      gapWidth: gapWidth(type, data),
      overlap: barOverlap(type, data),
      colors: { series: seriesColors(data.series.length), points: pointColors(figure, type, data), grid: "var(--line)", background: "var(--bg)" },
      text: { category: ".kit-category", legend: ".kit-legend > span, .kit-donut-legend span", share: ".kit-donut-legend b", axisTitle: ".kit-axis-title" },
    };
  }

  function chartFigure(slide) {
    return slide.getAttribute("data-layout") === "chart" ? slide.querySelector(":scope > figure[data-chart]") : null;
  }

  function composeChartSide(slide) {
    const figure = chartFigure(slide);
    const legend = figure?.querySelector(".kit-donut-legend");
    if (!legend) return;
    const side = element("div", "kit-side");
    slide.insertBefore(side, figure.nextSibling);
    side.append(legend, ...directChildren(slide, "insight"), ...directChildren(slide, "takeaway"));
    slide.classList.add("kit-round-side");
  }

  function unsquareRings(rings) {
    rings.forEach((ring) => {
      ring.classList.remove("kit-squared");
      ["width", "height"].forEach((name) => ring.style.removeProperty(name));
    });
  }

  function squareRing(ring, side) {
    ring.style.setProperty("width", `${Math.floor(side)}px`);
    ring.style.setProperty("height", `${Math.floor(side)}px`);
    ring.classList.add("kit-squared");
  }

  async function squareRings(slide, layOut) {
    const rings = Array.from(slide.querySelectorAll(".kit-donut-ring"));
    if (!rings.length) return;
    unsquareRings(rings);
    if (layOut) await layOut(slide);
    rings.forEach((ring) => {
      const box = ring.getBoundingClientRect();
      squareRing(ring, Math.min(box.width, box.height));
    });
    if (layOut) await layOut(slide);
  }

  function boxSize(target) {
    const box = target.getBoundingClientRect();
    return { width: box.right - box.left, height: box.bottom - box.top };
  }

  function frameWidth(slide) {
    const style = getComputedStyle(slide);
    return slide.offsetWidth - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0);
  }

  function columnGap(slide) {
    return parseFloat(getComputedStyle(slide).columnGap) || 0;
  }

  function naturalPlotWidth(figure, plot) {
    const type = figure.getAttribute("data-chart");
    const data = chartData(figure);
    const columnData = type === "combo" ? { labels: data.labels, series: data.series.slice(0, -1) } : data;
    const bars = barsPerGroup(columnData.series.length, type === "stacked" || type === "stacked100");
    const { width, height } = boxSize(plot);
    const thickest = height * barDepthShare;
    const band = (thickest * bars) / (bandFill(bars) * barShareOfSlot(bars));
    return Math.min(width, band * columnData.labels.length);
  }

  async function fitColumnChart(slide, figure, layOut) {
    const plot = figure.querySelector(".kit-plot-area");
    if (!plot) return;
    const narrowest = frameWidth(slide) * chartShareMinimum;
    for (let pass = 0; pass < chartFitPasses; pass += 1) {
      const figureWidth = boxSize(figure).width;
      const plotWidth = boxSize(plot).width;
      const natural = Math.max(naturalPlotWidth(figure, plot), narrowest - (figureWidth - plotWidth));
      const freed = plotWidth - natural;
      if (freed < chartFitTolerance) break;
      slide.style.setProperty("--chart-width", `${Math.floor(figureWidth - freed)}px`);
      slide.classList.add("kit-fitted-chart");
      if (layOut) await layOut(slide);
    }
    await fitInsightValues(slide, layOut);
  }

  async function fitInsightValues(slide, layOut) {
    if (!slide.classList.contains("kit-fitted-chart")) return;
    const values = directChildren(slide, "insight").flatMap((insight) => directChildren(insight, "value"));
    values.forEach((value) => value.style.removeProperty("font-size"));
    if (layOut) await layOut(slide);
    values.forEach((value) => {
      if (value.scrollWidth <= value.clientWidth) return;
      const size = parseFloat(getComputedStyle(value).fontSize);
      value.style.setProperty("font-size", `${Math.floor((size * value.clientWidth) / value.scrollWidth)}px`);
    });
    if (layOut) await layOut(slide);
  }

  async function fitRoundChart(slide, figure, layOut) {
    const rings = Array.from(figure.querySelectorAll(".kit-donut-ring"));
    const widest = frameWidth(slide) - roundSideMinimum - columnGap(slide);
    for (let pass = 0; pass < chartFitPasses; pass += 1) {
      unsquareRings(rings);
      if (layOut) await layOut(slide);
      const diameter = Math.min(widest, ...rings.map((ring) => boxSize(ring).height));
      rings.forEach((ring) => squareRing(ring, diameter));
      slide.style.setProperty("--chart-width", `${Math.floor(diameter)}px`);
      slide.classList.add("kit-fitted-chart");
      if (layOut) await layOut(slide);
    }
  }

  function resetChartFit(slide) {
    slide.classList.remove("kit-fitted-chart");
    slide.style.removeProperty("--chart-width");
    slide.querySelectorAll(".insight > .value").forEach((value) => value.style.removeProperty("font-size"));
    unsquareRings(Array.from(slide.querySelectorAll(".kit-donut-ring")));
    const side = chartSide(slide);
    if (side) ["min-height", "margin-top"].forEach((name) => side.style.removeProperty(name));
  }

  function chartSide(slide) {
    if (!chartFigure(slide)) return null;
    return directChildren(slide, "kit-side")[0] || directChildren(slide, "insight")[0] || null;
  }

  function chartBottom(figure) {
    const drawn = Array.from(figure.children).filter((child) => child.tagName !== "FIGCAPTION");
    return Math.max(...drawn.map((child) => child.getBoundingClientRect().bottom));
  }

  async function spanChartSide(slide, layOut) {
    const side = chartSide(slide);
    if (!side) return;
    const box = side.getBoundingClientRect();
    const reach = chartBottom(chartFigure(slide)) - box.top;
    if (side.classList.contains("kit-side")) side.style.setProperty("min-height", `${Math.floor(reach)}px`);
    else centreBeside(side, reach - (box.bottom - box.top));
    if (layOut) await layOut(slide);
  }

  function centreBeside(part, slack) {
    if (slack <= 0) return;
    const margin = parseFloat(getComputedStyle(part).marginTop) || 0;
    part.style.setProperty("margin-top", `${Math.floor(margin + slack / 2)}px`);
  }

  async function fitTickGutters(slide, layOut) {
    const charts = Array.from(slide.querySelectorAll(".kit-scatter"));
    charts.forEach((chart) => chart.style.removeProperty("--tick-gutter"));
    if (!charts.length) return;
    if (layOut) await layOut(slide);
    charts.forEach((chart) => {
      const widest = Math.max(0, ...Array.from(chart.querySelectorAll(".kit-tick")).map((tick) => boxSize(tick).width));
      chart.style.setProperty("--tick-gutter", `${Math.ceil(widest)}px`);
    });
    if (layOut) await layOut(slide);
  }

  async function fitChart(slide, layOut) {
    await fitTickGutters(slide, layOut);
    const figure = chartFigure(slide);
    if (!figure) return squareRings(slide, layOut);
    const type = figure.getAttribute("data-chart");
    if (roundKinds.has(type)) return fitRoundChart(slide, figure, layOut);
    if (columnKinds.has(type)) return fitColumnChart(slide, figure, layOut);
  }

  function moveThemeToRoot() {
    const theme = document.body.getAttribute("data-theme");
    if (!theme) return;
    document.documentElement.setAttribute("data-theme", theme);
    document.body.removeAttribute("data-theme");
  }

  function applyAccent() {
    const accent = document.body.getAttribute("data-accent");
    if (accent) document.body.style.setProperty("--accent", accent);
  }

  function prepare() {
    if (document.body.getAttribute("data-kit-prepared")) return;
    document.body.setAttribute("data-kit-prepared", "true");
    moveThemeToRoot();
    applyAccent();
    addFooters();
    markStructure();
    buildDiagrams();
    drawIcons();
    addListIndexes();
    groupComparisonPoints();
    groupSteps();
    addCoverRings();
    addQuoteMarks();
    markNumericCells();
    keepMixedWords();
    trackHangul();
    document.querySelectorAll("section[data-layout] figure[data-chart]").forEach(renderChart);
    slides().forEach(composeChartSide);
  }

  async function render(layOut) {
    prepare();
    for (const slide of slides()) {
      resetChartFit(slide);
      clearItemBounds(slide);
      await fitSlide(slide, layOut);
      await boundItemSlack(slide, layOut);
      await balanceTitles(slide, layOut);
      await fitChart(slide, layOut);
      await spanChartSide(slide, layOut);
      drawConnectors(slide);
    }
  }

  async function renderWhenFontsLoad() {
    if (document.fonts) await document.fonts.ready;
    await render();
  }

  function start() {
    window.deckKit.ready = renderWhenFontsLoad();
  }

  window.deckKit = { render, ready: null, chartTypes: Object.keys(chartRenderers) };
  window.renderHook = render;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
