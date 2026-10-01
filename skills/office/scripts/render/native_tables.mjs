export const nativeTableAttribute = "data-internkim-pptx-table";
export const nativeCellAttribute = "data-internkim-pptx-cell";

export function extractNativeTables({ pages }) {
  const round = (value) => Math.round(value * 100) / 100;
  const pixels = (value) => parseFloat(value) || 0;
  const anchors = { top: "t", middle: "ctr", bottom: "b" };
  const sides = ["Top", "Right", "Bottom", "Left"];

  const colorAlpha = (color) => {
    if (!color || color === "transparent") return 0;
    const slash = color.match(/\/\s*([\d.]+)(%?)\s*\)$/);
    if (slash) return slash[2] ? parseFloat(slash[1]) / 100 : parseFloat(slash[1]);
    const legacy = color.match(/^rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\s*\)$/);
    return legacy ? parseFloat(legacy[1]) : 1;
  };

  const rowsOf = (table) => Array.from(table.querySelectorAll("tr")).filter((row) => row.closest("table") === table);

  const cellsOf = (row) => Array.from(row.children).filter((cell) => cell.tagName === "TD" || cell.tagName === "TH");

  const isPlainGrid = (table) => {
    const rows = rowsOf(table);
    if (!rows.length || table.querySelector("table")) return false;
    const width = cellsOf(rows[0]).length;
    const spansOne = (cell) => ["colspan", "rowspan"].every((name) => !cell.hasAttribute(name) || Number(cell.getAttribute(name)) === 1);
    return width > 0 && rows.every((row) => cellsOf(row).length === width && cellsOf(row).every(spansOne));
  };

  const isDrawn = (table) => {
    const style = getComputedStyle(table);
    return style.display !== "none" && style.visibility === "visible" && style.transform === "none";
  };

  const borderOf = (style, side) => {
    const width = pixels(style[`border${side}Width`]);
    const color = style[`border${side}Color`];
    const visible = width > 0 && !["none", "hidden"].includes(style[`border${side}Style`]) && colorAlpha(color) > 0;
    return visible ? { widthPx: round(width), color } : null;
  };

  const describeCell = (cell, address) => {
    const style = getComputedStyle(cell);
    const rowStyle = getComputedStyle(cell.parentElement);
    cell.setAttribute(nativeCellAttribute, address);
    const fill = [style.backgroundColor, rowStyle.backgroundColor].find((color) => colorAlpha(color) > 0) || null;
    return {
      address,
      fill,
      borders: Object.fromEntries(sides.map((side) => [side.toLowerCase(), borderOf(style, side)])),
      insets: { left: round(pixels(style.paddingLeft)), top: round(pixels(style.paddingTop)), right: round(pixels(style.paddingRight)), bottom: round(pixels(style.paddingBottom)) },
      anchor: anchors[style.verticalAlign] || "t",
    };
  };

  const relative = (rect, origin) => ({ left: round(rect.left - origin.left), top: round(rect.top - origin.top), right: round(rect.right - origin.left), bottom: round(rect.bottom - origin.top) });

  const describeTable = (table, tableId, origin) => {
    table.setAttribute(nativeTableAttribute, tableId);
    const rows = rowsOf(table);
    return {
      id: tableId,
      box: relative(table.getBoundingClientRect(), origin),
      columnWidthsPx: cellsOf(rows[0]).map((cell) => round(cell.getBoundingClientRect().width)),
      rows: rows.map((row, rowIndex) => ({
        heightPx: round(row.getBoundingClientRect().height),
        cells: cellsOf(row).map((cell, columnIndex) => describeCell(cell, `${tableId}:${rowIndex}:${columnIndex}`)),
      })),
    };
  };

  return pages.map((page, pageIndex) => {
    const origin = page.getBoundingClientRect();
    const tables = Array.from(page.querySelectorAll("table")).filter((table) => isDrawn(table) && isPlainGrid(table));
    return { tables: tables.map((table, index) => describeTable(table, `${pageIndex + 1}.${index + 1}`, origin)) };
  });
}

export function hideNativeTables() {
  const selectors = ["", " thead", " tbody", " tfoot", " tr", " td", " th"].map((descendant) => `[${nativeTableAttribute}]${descendant}`);
  const stylesheet = document.createElement("style");
  stylesheet.textContent = `${selectors.join(", ")} { background-color: transparent !important; background-image: none !important; border-color: transparent !important; box-shadow: none !important; }`;
  document.head.appendChild(stylesheet);
}
