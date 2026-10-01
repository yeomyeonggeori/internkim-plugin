(() => {
  const fitSteps = [1, 0.95, 0.9, 0.86, 0.82, 0.78];
  const overflowTolerance = 2;
  const footerlessLayouts = new Set(["cover", "section"]);
  const itemClasses = ["kpi", "card", "step", "column"];
  const numericCellPattern = /^[+\-−]?[₩$€£¥]?\s?[\d.,]+\s?(%|%p|[^\s\d]{0,4})?$/;
  const svgNamespace = "http://www.w3.org/2000/svg";
  const barScaleShare = 0.84;
  const lineInsetShare = 5;
  const coverRingRadii = [442, 342, 242];
  const groupedNumberPattern = /^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$/;

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
      const source = directChildren(slide, "source")[0];
      if (source) {
        footer.appendChild(source);
      } else {
        const label = element("span", "source");
        label.textContent = deckLabel;
        footer.appendChild(label);
      }
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
      if (directChildren(slide, "insight").length) slide.classList.add("kit-with-insight");
      const hasBody = Array.from(slide.children).some((child) => child.classList.contains("card") || ["OL", "UL"].includes(child.tagName));
      if (!hasBody) slide.classList.add("kit-bare");
    });
  }

  function addListIndexes() {
    const lists = Array.from(document.querySelectorAll("section[data-layout] ol, section[data-layout='agenda'] > ul"));
    lists.forEach((list) => {
      Array.from(list.children).forEach((item, position) => {
        if (item.firstElementChild?.classList.contains("kit-index")) return;
        const index = element("span", "kit-index");
        index.textContent = String(position + 1).padStart(2, "0");
        item.insertBefore(index, item.firstChild);
      });
    });
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
    });
  }

  function markNumericCells() {
    document.querySelectorAll("section[data-layout] table").forEach((table) => {
      const rows = Array.from(table.querySelectorAll("tr"));
      rows.forEach((row) => Array.from(row.children).forEach((cell) => {
        if (cell.tagName === "TD" && numericCellPattern.test(cell.textContent.trim())) cell.classList.add("kit-number");
      }));
      const width = Math.max(0, ...rows.map((row) => row.children.length));
      for (let column = 0; column < width; column += 1) {
        const cells = rows.map((row) => row.children[column]).filter(Boolean);
        const data = cells.filter((cell) => cell.tagName === "TD");
        if (data.length && data.every((cell) => cell.classList.contains("kit-number"))) cells.forEach((cell) => cell.classList.add("kit-number"));
      }
    });
  }

  function overflows(slide) {
    if (slide.scrollHeight > slide.clientHeight + overflowTolerance || slide.scrollWidth > slide.clientWidth + overflowTolerance) return true;
    return Array.from(slide.querySelectorAll("*")).some((child) => {
      if (child.closest("aside.notes, .kit-chart") || child.clientHeight === 0) return false;
      return child.scrollHeight > child.clientHeight + overflowTolerance || child.scrollWidth > child.clientWidth + overflowTolerance;
    });
  }

  async function fitSlide(slide, layOut) {
    for (const step of fitSteps) {
      slide.style.setProperty("--fit", String(step));
      if (layOut) await layOut(slide);
      if (!slide.clientHeight || !overflows(slide)) return;
    }
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

  function formatterFor(figure, series) {
    const decimals = decimalsOf(series);
    const formatter = new Intl.NumberFormat(locale(), { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
    const unit = figure.getAttribute("data-unit") || "";
    return (value) => formatter.format(value) + unit;
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

  function niceRange(values, includeZero) {
    let minimum = Math.min(...values);
    let maximum = Math.max(...values);
    if (includeZero) {
      minimum = Math.min(0, minimum);
      maximum = Math.max(0, maximum);
    } else {
      const padding = (maximum - minimum || Math.abs(maximum) || 1) * 0.25;
      minimum -= padding;
      maximum += padding * 0.6;
    }
    if (maximum === minimum) maximum = minimum + 1;
    return { minimum, maximum, share: (value) => (value - minimum) / (maximum - minimum) };
  }

  function isMuted(figure, data, label) {
    const highlight = figure.getAttribute("data-highlight");
    return data.series.length === 1 && Boolean(highlight) && label !== highlight;
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
      if (point.below) label.setAttribute("data-below", "");
    }
    return label;
  }

  function groupShare(categoryCount) {
    if (categoryCount <= 3) return 0.34;
    return categoryCount <= 6 ? 0.5 : 0.62;
  }

  function barGroupShare(seriesCount) {
    return seriesCount === 1 ? 0.56 : 0.72;
  }

  function lineStartsAtZero(figure) {
    return figure.getAttribute("data-zero") === "true";
  }

  function renderColumns(figure, data, chart, format, stacked) {
    const area = element("div", "kit-plot-area");
    const categories = element("div", "kit-categories");
    chart.append(area, categories);
    const colors = seriesColors(data.series.length);
    const totals = data.labels.map((_, category) => data.series.reduce((sum, item) => sum + Math.max(0, item.values[category]), 0));
    const range = niceRange(stacked ? totals : data.series.flatMap((item) => item.values), true);
    const top = (value) => (1 - range.share(value)) * 100;
    const zero = top(0);
    const slot = 100 / data.labels.length;
    const group = slot * groupShare(data.labels.length);
    const barWidth = stacked ? group : group / data.series.length;
    data.labels.forEach((label, category) => {
      const center = slot * category + slot / 2;
      const left = center - group / 2;
      if (stacked) {
        let stackTop = zero;
        data.series.forEach((item, seriesIndex) => {
          const value = Math.max(0, item.values[category]);
          const height = zero - top(value);
          stackTop -= height;
          area.appendChild(element("div", "kit-segment", { left: percent(left), top: percent(stackTop), width: percent(barWidth), height: percent(height), background: colors[seriesIndex] }));
          if (height >= 7 && seriesIndex < 2) {
            const inside = valueLabel(format(value), seriesIndex === 0 ? "kit-inside" : "kit-inside kit-on-light", { left: percent(center), top: percent(stackTop + height / 2) }, { series: seriesIndex, index: category });
            area.appendChild(inside);
          }
        });
        area.appendChild(valueLabel(format(totals[category]), "", { left: percent(center), top: percent(stackTop) }));
      } else {
        data.series.forEach((item, seriesIndex) => {
          const value = item.values[category];
          const barLeft = left + seriesIndex * barWidth;
          const barTop = Math.min(top(value), zero);
          const height = Math.max(0.3, Math.abs(zero - top(value)));
          const negative = value < 0 ? " kit-negative" : "";
          area.appendChild(element("div", `kit-bar${negative}`, { left: percent(barLeft + barWidth * 0.06), top: percent(barTop), width: percent(barWidth * 0.88), height: percent(height), background: barColor(figure, data, seriesIndex, label, colors) }));
          const muted = isMuted(figure, data, label) ? " kit-muted" : "";
          area.appendChild(valueLabel(format(value), `${value < 0 ? "kit-below" : ""}${muted}`, { left: percent(barLeft + barWidth / 2), top: percent(value < 0 ? barTop + height : barTop) }, { series: seriesIndex, index: category }));
        });
      }
      const categoryLabel = element("span", "kit-category", { left: percent(center) });
      categoryLabel.textContent = label;
      categories.appendChild(categoryLabel);
    });
    area.appendChild(element("div", "kit-baseline", { top: percent(zero) }));
  }

  function renderBars(figure, data, chart, format) {
    const rows = element("div", "kit-bar-rows");
    chart.appendChild(rows);
    const colors = seriesColors(data.series.length);
    const range = niceRange(data.series.flatMap((item) => item.values), true);
    const slot = 100 / data.labels.length;
    const group = slot * barGroupShare(data.series.length);
    const barHeight = group / data.series.length;
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
        area.appendChild(element("div", `kit-bar kit-horizontal${negative}`, { left: percent(left), top: percent(barTop + barHeight * 0.06), width: percent(width), height: percent(barHeight * 0.88), background: barColor(figure, data, seriesIndex, label, colors) }));
        const muted = isMuted(figure, data, label) ? " kit-muted" : "";
        area.appendChild(valueLabel(format(value), `${value < 0 ? "kit-start" : "kit-end"}${muted}`, { left: percent(value < 0 ? left : left + width), top: percent(barTop + barHeight / 2) }, { series: seriesIndex, index: category }));
      });
    });
    area.appendChild(element("div", "kit-baseline kit-vertical", { left: percent(zero) }));
  }

  function renderLine(figure, data, chart, format) {
    const area = element("div", "kit-plot-area kit-line-area");
    const categories = element("div", "kit-categories kit-line-categories");
    chart.append(area, categories);
    const colors = seriesColors(data.series.length);
    const range = niceRange(data.series.flatMap((item) => item.values), lineStartsAtZero(figure));
    const xOf = (index) => (data.labels.length === 1 ? 50 : lineInsetShare + (index * (100 - 2 * lineInsetShare)) / (data.labels.length - 1));
    const yOf = (value) => (1 - range.share(value)) * 100;
    [0, 50, 100].forEach((share) => area.appendChild(element("div", "kit-gridline", { top: percent(share) })));
    const labelEveryPoint = data.series.length <= 2 && data.labels.length <= 8;
    data.series.forEach((item, seriesIndex) => {
      const points = item.values.map((value, index) => [xOf(index) * 10, yOf(value) * 10]);
      const outline = points.map((point) => point.join(",")).join(" ");
      const shapes = [svgElement("polyline", { points: outline, fill: "none", stroke: "currentColor", "stroke-width": 5, "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" })];
      if (data.series.length === 1) {
        shapes.unshift(svgElement("path", { d: `M${points[0][0]},1000 L${outline.split(" ").join(" L")} L${points[points.length - 1][0]},1000 Z`, fill: "currentColor", "fill-opacity": 0.1 }));
      }
      area.appendChild(svgLayer(colors[seriesIndex], "0 0 1000 1000", "none", shapes));
    });
    data.series.forEach((item, seriesIndex) => {
      item.values.forEach((value, index) => {
        const isLast = index === item.values.length - 1;
        const position = { left: percent(xOf(index)), top: percent(yOf(value)) };
        area.appendChild(element("i", `kit-dot${isLast ? " kit-last" : ""}`, { ...position, "border-color": colors[seriesIndex], background: isLast ? colors[seriesIndex] : "var(--bg)" }));
        if (!labelEveryPoint && !isLast) return;
        const below = data.series.length === 2 && seriesIndex === 1 && value < data.series[0].values[index];
        area.appendChild(valueLabel(format(value), `${below ? "kit-below" : ""}${isLast ? "" : " kit-muted"}`, position, { series: seriesIndex, index, below }));
      });
    });
    data.labels.forEach((label, index) => {
      const categoryLabel = element("span", "kit-category", { left: percent(xOf(index)) });
      categoryLabel.textContent = label;
      categories.appendChild(categoryLabel);
    });
    area.appendChild(element("div", "kit-baseline kit-faint", { top: "100%" }));
  }

  function donutCenter(figure, data) {
    const values = data.series[0].values;
    const total = values.reduce((sum, value) => sum + value, 0);
    return figure.getAttribute("data-center") || `${Math.round((values[0] / total) * 100)}%`;
  }

  function donutCenterLabel(figure, data) {
    return figure.getAttribute("data-center-label") || data.labels[0];
  }

  function renderDonut(figure, data, chart, format, isPie) {
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
    const valuesAreShares = (figure.getAttribute("data-unit") || "").trim() === "%";
    data.labels.forEach((label, index) => {
      const row = element("div");
      const name = element("span");
      name.textContent = label;
      const amount = element("b");
      amount.textContent = format(values[index]);
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
    column: (figure, data, chart, format) => renderColumns(figure, data, chart, format, false),
    stacked: (figure, data, chart, format) => renderColumns(figure, data, chart, format, true),
    bar: (figure, data, chart, format) => renderBars(figure, data, chart, format),
    line: (figure, data, chart, format) => renderLine(figure, data, chart, format),
    donut: (figure, data, chart, format) => renderDonut(figure, data, chart, format, false),
    pie: (figure, data, chart, format) => renderDonut(figure, data, chart, format, true),
  };

  function renderChart(figure) {
    Array.from(figure.children).filter((child) => child.classList.contains("kit-chart")).forEach((previous) => previous.remove());
    const type = figure.getAttribute("data-chart");
    const renderer = chartRenderers[type];
    if (!renderer) return;
    const data = chartData(figure);
    const chart = element("div", `kit-chart kit-chart-${type}`);
    figure.insertBefore(chart, figure.firstChild);
    if (data.series.length > 1) chart.appendChild(legendFor(data.series, seriesColors(data.series.length)));
    renderer(figure, data, chart, formatterFor(figure, data.series));
    chart.setAttribute("data-native-chart", "");
    chart.nativeChart = nativeChart(figure, type, data);
  }

  function rangeLimits(range) {
    return { minimum: range.minimum, maximum: range.maximum };
  }

  function gapWidth(type, data) {
    const share = type === "bar" ? barGroupShare(data.series.length) : groupShare(data.labels.length);
    return Math.round(((1 - share) / share) * 100);
  }

  function pointColors(figure, type, data) {
    if (type === "donut" || type === "pie") return [seriesColors(data.labels.length)];
    const colors = seriesColors(data.series.length);
    const usesHighlight = type === "column" || type === "bar";
    return data.series.map((_, seriesIndex) => data.labels.map((label) => (usesHighlight ? barColor(figure, data, seriesIndex, label, colors) : colors[seriesIndex])));
  }

  function nativeChart(figure, type, data) {
    return {
      type,
      labels: data.labels,
      series: data.series,
      unit: figure.getAttribute("data-unit") || "",
      decimals: decimalsOf(data.series),
      startsAtZero: type !== "line" || lineStartsAtZero(figure),
      valueRange: type === "line" ? rangeLimits(niceRange(data.series.flatMap((item) => item.values), lineStartsAtZero(figure))) : null,
      gapWidth: gapWidth(type, data),
      colors: { series: seriesColors(data.series.length), points: pointColors(figure, type, data), grid: "var(--line)", background: "var(--bg)" },
      text: { category: ".kit-category", legend: ".kit-legend > span, .kit-donut-legend span", share: ".kit-donut-legend b" },
    };
  }

  function applyAccent() {
    const accent = document.body.getAttribute("data-accent");
    if (accent) document.body.style.setProperty("--accent", accent);
  }

  function prepare() {
    if (document.body.getAttribute("data-kit-prepared")) return;
    document.body.setAttribute("data-kit-prepared", "true");
    applyAccent();
    addFooters();
    markStructure();
    addListIndexes();
    groupSteps();
    addCoverRings();
    addQuoteMarks();
    markNumericCells();
    document.querySelectorAll("section[data-layout] figure[data-chart]").forEach(renderChart);
  }

  async function render(layOut) {
    prepare();
    for (const slide of slides()) await fitSlide(slide, layOut);
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
