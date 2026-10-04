(() => {
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
  const coverBleedRatio = 1.3;
  const coverFigureClass = "kpi";
  const coverLogoHeight = 44;
  const footerLogoHeight = 24;
  const backdropSelector = ".kit-scrim, .kit-cover-bleed > img:not(.kit-logo), .kit-logo";
  const groupedNumberPattern = /^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$/;
  const twoAxisTypes = new Set(["combo", "scatter"]);
  const separateAxisRatio = 10;
  const belowLabelShare = 0.12;
  const insideLabelSeries = 3;
  const insideLabelInks = ["var(--on-accent)", "var(--text)", "var(--ground)"];
  const scatterLabelSwitchShare = 70;
  const edgeTickClasses = { 0: "kit-from-start", 100: "kit-from-end" };
  const tickIntervals = 4;
  const roundStepMultiples = [1, 2, 5, 10];
  const iconAttribute = "data-icon";
  const iconHostClasses = ["card", "kpi", "step"];
  const iconListLayouts = ["agenda", "closing"];
  const nativeIconAttribute = "data-native-icon";
  const logoContrastMinimum = 3;
  function slides() {
    return Array.from(document.querySelectorAll("section"));
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
    const palette = ["var(--accent)", "var(--secondary)", "var(--chart-muted)", "var(--muted)", "color-mix(in srgb, var(--accent) 45%, var(--ground))", "color-mix(in srgb, var(--secondary) 45%, var(--ground))", "var(--text-soft)", "var(--line)"];
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

  function withRoomBelow(low, high) {
    return low < 0 ? low - (high - low) * belowLabelShare : low;
  }

  function niceRange(values, includeZero) {
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    if (includeZero) return scaledRange(withRoomBelow(Math.min(0, minimum), Math.max(0, maximum)), Math.max(0, maximum));
    const padding = (maximum - minimum || Math.abs(maximum) || 1) * 0.25;
    return scaledRange(minimum - padding, maximum + padding * 0.6);
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
    return niceRange(data.series.flatMap((item) => item.values), true);
  }

  function renderColumns(figure, data, chart, formats, mode, fixedRange) {
    const { area, categories } = categoryAxis(chart, "");
    const colors = seriesColors(data.series.length);
    const stacks = mode === "stacked" || mode === "percent";
    const totals = data.labels.map((_, category) => data.series.reduce((sum, item) => sum + Math.max(0, item.values[category]), 0));
    const range = fixedRange || columnRange(data, mode, totals);
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
      area.appendChild(element("i", `kit-dot${isLast ? " kit-last" : ""}`, { left: percent(point.x), top: percent(point.y), "border-color": color, background: isLast ? color : "var(--ground)" }));
    });
  }

  function lineLabels(values, seriesIndex, format, position, labelEveryPoint, isBelow, inkOver = () => null) {
    return values.flatMap((value, index) => {
      const isLast = index === values.length - 1;
      if (!labelEveryPoint && !isLast) return [];
      const point = position(index, value);
      const below = isBelow(index, value);
      const ink = inkOver(index, point.y);
      const placement = { left: percent(point.x), top: percent(point.y), ...(ink ? { color: ink } : {}) };
      return [valueLabel(format(value), `${below ? "kit-below" : ""}${isLast || ink ? "" : " kit-muted"}`, placement, { series: seriesIndex, index, position: below ? "b" : "t" })];
    });
  }

  function columnInkOver(figure, columns, columnScale, colors) {
    const top = (value) => (1 - columnScale.share(value)) * 100;
    return (index, y) => {
      const covering = columns.series.findIndex((item) => {
        const [upper, lower] = [top(Math.max(0, item.values[index])), top(Math.min(0, item.values[index]))];
        return upper < y && y < lower;
      });
      return covering < 0 ? null : insideLabelInk(figure, colors[covering]);
    };
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

  function largestMagnitude(values) {
    return Math.max(0, ...values.map(Math.abs));
  }

  function lineNeedsOwnAxis(columnValues, lineValues, unitsDiffer) {
    if (unitsDiffer) return true;
    const columns = largestMagnitude(columnValues);
    const line = largestMagnitude(lineValues);
    if (!columns || !line) return false;
    return Math.max(columns, line) / Math.min(columns, line) > separateAxisRatio;
  }

  function stepsBeyond(extent, step) {
    return extent > 0 ? Math.floor(extent / step) + 1 : 0;
  }

  function zeroAlignedRanges(groups) {
    const steps = groups.map((values) => roundStep((Math.max(0, ...values) - Math.min(0, ...values)) / tickIntervals || 1));
    const below = Math.max(...groups.map((values, index) => stepsBeyond(-withRoomBelow(Math.min(0, ...values), Math.max(0, ...values)), steps[index])));
    const above = Math.max(...groups.map((values, index) => stepsBeyond(Math.max(0, ...values), steps[index]))) || (below ? 0 : 1);
    return steps.map((step) => ({ ...scaledRange(-below * step, above * step), step }));
  }

  function comboRanges(columnValues, lineValues, ownAxis) {
    if (ownAxis) return zeroAlignedRanges([columnValues, lineValues]);
    const shared = zeroAlignedRanges([[...columnValues, ...lineValues]])[0];
    return [shared, shared];
  }

  function addRightTicks(chart, area, range, unit) {
    chart.classList.add("kit-right-axis");
    const row = element("div", "kit-axis-row");
    const rail = element("div", "kit-tick-rail");
    area.replaceWith(row);
    row.append(area, rail);
    axisTicks(range, unit).forEach(({ share, text }) => {
      const tick = element("span", `kit-tick kit-right ${edgeTickClasses[100 - share] || ""}`.trim(), { top: percent(100 - share) });
      tick.textContent = text;
      rail.appendChild(tick);
    });
  }

  function renderCombo(figure, data, chart, formats) {
    const columns = { labels: data.labels, series: data.series.slice(0, -1) };
    const line = data.series[data.series.length - 1];
    const lineIndex = data.series.length - 1;
    const color = seriesColors(data.series.length)[lineIndex];
    const columnValues = columns.series.flatMap((item) => item.values);
    const ownAxis = lineNeedsOwnAxis(columnValues, line.values, formats[0].unit !== formats[lineIndex].unit);
    const [columnScale, lineScale] = comboRanges(columnValues, line.values, ownAxis);
    const { area, xOf } = renderColumns(figure, columns, chart, formats, "combo", columnScale);
    const position = (index, value) => ({ x: xOf(index), y: (1 - lineScale.share(value)) * 100 });
    const points = line.values.map((value, index) => [position(index, value).x * 10, position(index, value).y * 10]);
    area.appendChild(polylineLayer(color, points, false));
    addDots(area, line.values, color, position);
    const inkOver = columnInkOver(figure, columns, columnScale, seriesColors(data.series.length));
    lineLabels(line.values, lineIndex, formats[lineIndex].format, position, data.labels.length <= 8, (index, value) => value < 0, inkOver).forEach((label) => area.appendChild(label));
    if (ownAxis) addRightTicks(chart, area, lineScale, formats[lineIndex].unit);
    chart.primaryRange = columnScale;
    chart.secondaryRange = ownAxis ? lineScale : null;
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
    if (!range) return null;
    return range.step ? { minimum: range.minimum, maximum: range.maximum, step: range.step } : { minimum: range.minimum, maximum: range.maximum };
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
      colors: { series: seriesColors(data.series.length), points: pointColors(figure, type, data), grid: "var(--line)", background: "var(--ground)" },
      text: { category: ".kit-category", legend: ".kit-legend > span, .kit-donut-legend span", share: ".kit-donut-legend b", axisTitle: ".kit-axis-title", tick: ".kit-tick" },
    };
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
  async function fitTickGutters(slide, layOut) {
    const charts = Array.from(slide.querySelectorAll(".kit-scatter, .kit-right-axis"));
    charts.forEach((chart) => chart.style.removeProperty("--tick-gutter"));
    if (!charts.length) return;
    if (layOut) await layOut(slide);
    charts.forEach((chart) => {
      const widest = Math.max(0, ...Array.from(chart.querySelectorAll(".kit-tick")).map((tick) => boxSize(tick).width));
      chart.style.setProperty("--tick-gutter", `${Math.ceil(widest)}px`);
    });
    if (layOut) await layOut(slide);
  }

  function drawIcons() {
    document.querySelectorAll(`[${iconAttribute}]`).forEach((host) => {
      const markup = (window.deckKitIcons || {})[(host.getAttribute(iconAttribute) || "").trim()];
      if (!markup || host.querySelector("svg")) return;
      host.classList.add("kit-icon");
      host.innerHTML = markup;
      host.setAttribute(nativeIconAttribute, host.getAttribute(iconAttribute).trim());
    });
  }

  function backdropChannels(image) {
    for (let parent = image.parentElement; parent; parent = parent.parentElement) {
      const parts = (getComputedStyle(parent).backgroundColor.match(/[\d.]+/g) || []).map(Number);
      if (parts.length >= 3 && (parts.length < 4 || parts[3] > 0)) return parts.slice(0, 3);
    }
    return [255, 255, 255];
  }

  function logoNeedsPlate(logo, image) {
    return !logo.hasTransparency || contrastRatio(logo.ink, backdropChannels(image)) < logoContrastMinimum;
  }

  const logoHeight = 56;
  const logoInset = 48;
  const logoCorners = [
    { bottom: logoInset, left: logoInset },
    { bottom: logoInset, right: logoInset },
    { top: logoInset, right: logoInset },
    { top: logoInset, left: logoInset },
  ];

  function logoSlides() {
    const all = slides();
    return all.length > 1 ? [all[0], all[all.length - 1]] : all;
  }

  function drawLogos() {
    const logo = window.deckKitLogo;
    document.querySelectorAll("img[data-logo]").forEach((image) => image.remove());
    if (!logo) return;
    logoSlides().forEach((slide) => {
      const image = document.createElement("img");
      image.classList.add("kit-logo");
      image.setAttribute("src", logo.src);
      image.setAttribute("alt", "");
      image.style.setProperty("aspect-ratio", String(logo.ratio));
      if (logoNeedsPlate(logo, image)) image.classList.add("kit-plated");
      if (getComputedStyle(slide).position === "static") slide.style.setProperty("position", "relative");
      slide.appendChild(image);
    });
  }

  function contentRects(slide, logoImage) {
    const rects = [];
    const range = document.createRange();
    const visit = (node) => {
      if (node.nodeType === 3) {
        if (!node.textContent.trim()) return;
        range.selectNodeContents(node);
        rects.push(...Array.from(range.getClientRects()));
        return;
      }
      if (node.nodeType === 1 && !node.matches("aside, .kit-logo")) Array.from(node.childNodes).forEach(visit);
    };
    visit(slide);
    slide.querySelectorAll("img, svg, canvas, table, figure").forEach((element) => {
      if (element !== logoImage && !element.closest("aside") && !element.parentElement.closest("svg")) rects.push(element.getBoundingClientRect());
    });
    return rects.filter((rect) => rect.width > 0 && rect.height > 0);
  }

  function overlaps(first, second) {
    return first.left < second.right && second.left < first.right && first.top < second.bottom && second.top < first.bottom;
  }

  function placeLogo(slide, corner) {
    const image = slide.querySelector("img.kit-logo");
    ["top", "right", "bottom", "left"].forEach((side) => image.style.removeProperty(side));
    image.style.setProperty("position", "absolute");
    image.style.setProperty("height", `${logoHeight}px`);
    Object.entries(corner).forEach(([side, value]) => image.style.setProperty(side, `${value}px`));
    return image;
  }

  async function placeLogos(layOut) {
    for (const slide of slides()) {
      if (!slide.querySelector("img.kit-logo")) continue;
      let chosen = logoCorners[0];
      for (const corner of logoCorners) {
        const image = placeLogo(slide, corner);
        if (layOut) await layOut(slide);
        chosen = corner;
        const box = image.getBoundingClientRect();
        if (!contentRects(slide, image).some((rect) => overlaps(box, rect))) break;
      }
      placeLogo(slide, chosen);
      if (layOut) await layOut(slide);
    }
  }

  function prepare() {
    if (document.body.getAttribute("data-kit-prepared")) return;
    document.body.setAttribute("data-kit-prepared", "true");
    drawIcons();
    drawLogos();
    document.querySelectorAll("section figure[data-chart]").forEach(renderChart);
  }

  async function render(layOut) {
    prepare();
    await placeLogos(layOut);
    for (const slide of slides()) {
      await fitTickGutters(slide, layOut);
      await squareRings(slide, layOut);
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
