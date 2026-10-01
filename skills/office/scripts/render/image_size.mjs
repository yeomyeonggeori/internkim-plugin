function pngSize(bytes) {
  if (bytes.length < 24 || bytes.toString("ascii", 1, 4) !== "PNG") return null;
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

function gifSize(bytes) {
  if (bytes.length < 10 || bytes.toString("ascii", 0, 3) !== "GIF") return null;
  return { width: bytes.readUInt16LE(6), height: bytes.readUInt16LE(8) };
}

function webpSize(bytes) {
  if (bytes.length < 30 || bytes.toString("ascii", 0, 4) !== "RIFF" || bytes.toString("ascii", 8, 12) !== "WEBP") return null;
  const chunk = bytes.toString("ascii", 12, 16);
  if (chunk === "VP8X") return { width: 1 + bytes.readUIntLE(24, 3), height: 1 + bytes.readUIntLE(27, 3) };
  if (chunk === "VP8L") {
    const bits = bytes.readUInt32LE(21);
    return { width: 1 + (bits & 0x3fff), height: 1 + ((bits >> 14) & 0x3fff) };
  }
  return { width: bytes.readUInt16LE(26) & 0x3fff, height: bytes.readUInt16LE(28) & 0x3fff };
}

const startOfFrameMarkers = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);

function jpegSize(bytes) {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  let offset = 2;
  while (offset + 9 < bytes.length) {
    if (bytes[offset] !== 0xff) return null;
    const marker = bytes[offset + 1];
    if (startOfFrameMarkers.has(marker)) return { width: bytes.readUInt16BE(offset + 7), height: bytes.readUInt16BE(offset + 5) };
    offset += 2 + bytes.readUInt16BE(offset + 2);
  }
  return null;
}

function svgSize(bytes) {
  const text = bytes.toString("utf8", 0, Math.min(bytes.length, 4096));
  if (!text.includes("<svg")) return null;
  const width = text.match(/<svg[^>]*\swidth="([\d.]+)(px)?"/);
  const height = text.match(/<svg[^>]*\sheight="([\d.]+)(px)?"/);
  if (width && height) return { width: parseFloat(width[1]), height: parseFloat(height[1]) };
  const viewBox = text.match(/viewBox="[\d.\-]+[\s,]+[\d.\-]+[\s,]+([\d.]+)[\s,]+([\d.]+)"/);
  return viewBox ? { width: parseFloat(viewBox[1]), height: parseFloat(viewBox[2]) } : null;
}

export function imageSize(bytes) {
  return pngSize(bytes) || jpegSize(bytes) || gifSize(bytes) || webpSize(bytes) || svgSize(bytes);
}

export function dataURIBytes(uri) {
  const comma = uri.indexOf(",");
  if (!uri.startsWith("data:") || comma < 0) return null;
  const header = uri.slice(5, comma);
  const payload = uri.slice(comma + 1);
  return header.endsWith(";base64") ? Buffer.from(payload, "base64") : Buffer.from(decodeURIComponent(payload), "utf8");
}
