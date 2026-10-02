export const nativeConnectorsAttribute = "data-native-connectors";

export function extractNativeConnectors({ pages }) {
  const round = (value) => Math.round(value * 100) / 100;
  const point = (value) => ({ x: round(value.x), y: round(value.y) });

  const describe = (connector, color) => ({
    start: point(connector.start),
    end: point(connector.end),
    sides: connector.sides,
    elbow: connector.elbow,
    arrow: connector.arrow,
    line: { color, widthPx: connector.widthPx },
    fromElement: connector.from,
    toElement: connector.to,
  });

  return pages.map((page) => {
    const layers = Array.from(page.querySelectorAll(`[${nativeConnectorsAttribute}]`)).filter((layer) => layer.nativeConnectors);
    const connectors = layers.flatMap((layer) => layer.nativeConnectors.map((connector) => describe(connector, getComputedStyle(layer).color)));
    layers.forEach((layer) => layer.remove());
    return connectors;
  });
}

export function attachConnectorShapes(pageConnectors, exportedShapeAttribute) {
  const exportIdOf = (element) => (element ? element.getAttribute(exportedShapeAttribute) : null);
  return pageConnectors.map((connectors) => ({
    connectors: connectors.map(({ fromElement, toElement, ...connector }) => ({ ...connector, fromShape: exportIdOf(fromElement), toShape: exportIdOf(toElement) })),
  }));
}
