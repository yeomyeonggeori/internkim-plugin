import { renderedFamilyResolver } from "./text_layout.mjs";

export const nativeChartAttribute = "data-native-chart";

export function extractNativeCharts({ pages }) {
  const familyOf = renderedFamilyResolver();
  const round = (value) => Math.round(value * 100) / 100;

  const resolvedColor = (host, value) => {
    const probe = document.createElement("i");
    probe.style.setProperty("color", value);
    host.appendChild(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  };

  const resolveColors = (host, value) => {
    if (typeof value === "string") return resolvedColor(host, value);
    if (Array.isArray(value)) return value.map((entry) => resolveColors(host, entry));
    return Object.fromEntries(Object.entries(value).map(([name, entry]) => [name, resolveColors(host, entry)]));
  };

  const textStyleOf = (element) => {
    const style = getComputedStyle(element);
    return { fontFamily: familyOf(style.fontFamily), fontWeight: parseInt(style.fontWeight, 10) || 400, sizePx: round(parseFloat(style.fontSize)), color: style.webkitTextFillColor || style.color };
  };

  const textStylesOf = (chart, selectors) =>
    Object.fromEntries(
      Object.entries(selectors || {}).flatMap(([role, selector]) => {
        const element = chart.querySelector(selector);
        return element ? [[role, textStyleOf(element)]] : [];
      }),
    );

  const pointLabelsOf = (chart) =>
    Array.from(chart.querySelectorAll("[data-series][data-point]")).map((label) => ({
      series: Number(label.getAttribute("data-series")),
      point: Number(label.getAttribute("data-point")),
      position: label.getAttribute("data-position") || "",
      text: textStyleOf(label),
    }));

  const ringOf = (chart) => chart.querySelector(".kit-donut-ring");

  const describe = (chart, origin) => {
    const { colors, text, ...data } = chart.nativeChart;
    const ring = ringOf(chart);
    const rect = (ring || chart).getBoundingClientRect();
    return {
      ...data,
      box: { left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) },
      colors: resolveColors(chart, colors || {}),
      text: { base: textStyleOf(chart), ...textStylesOf(chart, text) },
      pointLabels: pointLabelsOf(chart),
    };
  };

  const empty = (chart) => {
    const plot = ringOf(chart) || chart;
    const rect = plot.getBoundingClientRect();
    Array.from(plot.children).filter((child) => !child.matches(".kit-donut-center")).forEach((child) => child.remove());
    plot.style.setProperty("flex", "none");
    plot.style.setProperty("width", `${rect.width}px`);
    plot.style.setProperty("height", `${rect.height}px`);
  };

  return pages.map((page) => {
    const origin = page.getBoundingClientRect();
    const charts = Array.from(page.querySelectorAll(`[${nativeChartAttribute}]`)).filter((chart) => chart.nativeChart);
    const described = charts.map((chart) => describe(chart, origin));
    charts.forEach(empty);
    return { charts: described };
  });
}
