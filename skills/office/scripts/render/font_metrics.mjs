import { brotliDecompressSync } from "node:zlib";

const WOFF2_SIGNATURE = 0x774f4632;
const WOFF2_HEADER_LENGTH = 48;
const ARBITRARY_TAG_INDEX = 63;
// W3C WOFF2 §5.1, "Known Table Tags"
const WOFF2_KNOWN_TAGS = [
  "cmap", "head", "hhea", "hmtx", "maxp", "name", "OS/2", "post", "cvt ", "fpgm", "glyf", "loca", "prep", "CFF ", "VORG", "EBDT",
  "EBLC", "gasp", "hdmx", "kern", "LTSH", "PCLT", "VDMX", "vhea", "vmtx", "BASE", "GDEF", "GPOS", "GSUB", "EBSC", "JSTF", "MATH",
  "CBDT", "CBLC", "COLR", "CPAL", "SVG ", "sbix", "acnt", "avar", "bdat", "bloc", "bsln", "cvar", "fdsc", "feat", "fmtx", "fvar",
  "gvar", "hsty", "just", "lcar", "mort", "morx", "opbd", "prop", "trak", "Zapf", "Silf", "Glat", "Gloc", "Feat", "Sill",
];
const METRIC_TAGS = ["cmap", "head", "hhea", "hmtx"];

function tagAt(view, offset) {
  return String.fromCharCode(view.getUint8(offset), view.getUint8(offset + 1), view.getUint8(offset + 2), view.getUint8(offset + 3));
}

function sfntTables(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const tables = new Map();
  const count = view.getUint16(4);
  for (let index = 0; index < count; index += 1) {
    const record = 12 + index * 16;
    tables.set(tagAt(view, record), view.getUint32(record + 8));
  }
  return { view, tables };
}

function readBase128(view, cursor) {
  let value = 0;
  for (let index = 0; index < 5; index += 1) {
    const byte = view.getUint8(cursor.offset);
    cursor.offset += 1;
    value = value * 128 + (byte & 0x7f);
    if (!(byte & 0x80)) return value;
  }
  throw new Error("a WOFF2 table length runs past five bytes");
}

function isTransformed(tag, transformVersion) {
  return tag === "glyf" || tag === "loca" ? transformVersion !== 3 : transformVersion !== 0;
}

function woff2Directory(view) {
  const cursor = { offset: WOFF2_HEADER_LENGTH };
  return Array.from({ length: view.getUint16(12) }, () => {
    const flags = view.getUint8(cursor.offset);
    cursor.offset += 1;
    const tagIndex = flags & 0x3f;
    const tag = tagIndex === ARBITRARY_TAG_INDEX ? tagAt(view, cursor.offset) : WOFF2_KNOWN_TAGS[tagIndex];
    if (tagIndex === ARBITRARY_TAG_INDEX) cursor.offset += 4;
    const originalLength = readBase128(view, cursor);
    const transformed = isTransformed(tag, flags >> 6);
    const length = transformed ? readBase128(view, cursor) : originalLength;
    return { tag, length, transformed, end: cursor.offset };
  });
}

function woff2Tables(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const directory = woff2Directory(view);
  const streamStart = directory.at(-1).end;
  const stream = brotliDecompressSync(bytes.subarray(streamStart, streamStart + view.getUint32(20)));
  const tables = new Map();
  let offset = 0;
  for (const entry of directory) {
    if (METRIC_TAGS.includes(entry.tag) && entry.transformed) throw new Error(`the WOFF2 font stores its ${entry.tag} table transformed, which the layout cannot read`);
    tables.set(entry.tag, offset);
    offset += entry.length;
  }
  return { view: new DataView(stream.buffer, stream.byteOffset, stream.byteLength), tables };
}

function fontTables(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return view.getUint32(0) === WOFF2_SIGNATURE ? woff2Tables(bytes) : sfntTables(bytes);
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

export function readFontMetrics(bytes) {
  const { view, tables } = fontTables(bytes);
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
