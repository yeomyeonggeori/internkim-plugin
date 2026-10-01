import { readFileSync } from "node:fs";

function tableOffsets(view) {
  const tables = new Map();
  const count = view.getUint16(4);
  for (let index = 0; index < count; index += 1) {
    const record = 12 + index * 16;
    const tag = String.fromCharCode(view.getUint8(record), view.getUint8(record + 1), view.getUint8(record + 2), view.getUint8(record + 3));
    tables.set(tag, view.getUint32(record + 8));
  }
  return tables;
}

function glyphFromFormat4(view, subtable, codePoint) {
  if (codePoint > 0xffff) return 0;
  const segmentCount = view.getUint16(subtable + 6) / 2;
  const endCodes = subtable + 14;
  const startCodes = endCodes + segmentCount * 2 + 2;
  const deltas = startCodes + segmentCount * 2;
  const rangeOffsets = deltas + segmentCount * 2;
  for (let segment = 0; segment < segmentCount; segment += 1) {
    if (codePoint > view.getUint16(endCodes + segment * 2)) continue;
    const start = view.getUint16(startCodes + segment * 2);
    if (codePoint < start) return 0;
    const delta = view.getInt16(deltas + segment * 2);
    const rangeOffset = view.getUint16(rangeOffsets + segment * 2);
    if (rangeOffset === 0) return (codePoint + delta) & 0xffff;
    const glyph = view.getUint16(rangeOffsets + segment * 2 + rangeOffset + (codePoint - start) * 2);
    return glyph === 0 ? 0 : (glyph + delta) & 0xffff;
  }
  return 0;
}

function glyphFromFormat12(view, subtable, codePoint) {
  const groupCount = view.getUint32(subtable + 12);
  for (let group = 0; group < groupCount; group += 1) {
    const record = subtable + 16 + group * 12;
    const start = view.getUint32(record);
    const end = view.getUint32(record + 4);
    if (codePoint >= start && codePoint <= end) return view.getUint32(record + 8) + (codePoint - start);
  }
  return 0;
}

function glyphIndex(view, cmap, codePoint) {
  const subtableCount = view.getUint16(cmap + 2);
  let glyph = 0;
  for (let index = 0; index < subtableCount && !glyph; index += 1) {
    const subtable = cmap + view.getUint32(cmap + 4 + index * 8 + 4);
    const format = view.getUint16(subtable);
    if (format === 4) glyph = glyphFromFormat4(view, subtable, codePoint);
    if (format === 12) glyph = glyphFromFormat12(view, subtable, codePoint);
  }
  return glyph;
}

export function readFontMetrics(path) {
  const bytes = readFileSync(path);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const tables = tableOffsets(view);
  const unitsPerEm = view.getUint16(tables.get("head") + 18);
  const metricCount = view.getUint16(tables.get("hhea") + 34);
  const horizontalMetrics = tables.get("hmtx");
  const advanceOf = (glyph) => view.getUint16(horizontalMetrics + Math.min(glyph, metricCount - 1) * 4);
  return {
    advanceEm(codePoint) {
      const glyph = glyphIndex(view, tables.get("cmap"), codePoint);
      return glyph ? advanceOf(glyph) / unitsPerEm : null;
    },
  };
}
