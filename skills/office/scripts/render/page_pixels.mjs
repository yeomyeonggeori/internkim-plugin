const decorativeBandOccupancy = 0.85;
const decorativeBandMaximumDepthRatio = 0.15;
const backgroundColorDistanceLimit = 34;

function pixelAt(pixels, width, x, y) {
  const offset = (y * width + x) * 4;
  return [pixels[offset], pixels[offset + 1], pixels[offset + 2], pixels[offset + 3]];
}

function medianColor(samples) {
  return [0, 1, 2, 3].map((channel) => {
    const values = samples.map((sample) => sample[channel]).sort((first, second) => first - second);
    return values[Math.floor(values.length / 2)];
  });
}

function cornerBackgroundColor(pixels, width, height) {
  const sampleSize = Math.max(6, Math.floor(Math.min(width, height) / 40));
  const rows = [...Array(sampleSize).keys(), ...Array.from({ length: sampleSize }, (unused, index) => height - sampleSize + index)];
  const columns = [...Array(sampleSize).keys(), ...Array.from({ length: sampleSize }, (unused, index) => width - sampleSize + index)];
  const samples = [];
  for (const y of rows) for (const x of columns) samples.push(pixelAt(pixels, width, x, y));
  return medianColor(samples);
}

function isBackground(pixels, offset, background) {
  if (pixels[offset + 3] < 8) return true;
  const distance = Math.abs(pixels[offset] - background[0]) + Math.abs(pixels[offset + 1] - background[1]) + Math.abs(pixels[offset + 2] - background[2]);
  return distance <= backgroundColorDistanceLimit;
}

function contentRowSpans(pixels, width, height, background) {
  const columnCounts = new Array(width).fill(0);
  const rowSpans = [];
  let contentPixels = 0;
  for (let y = 0; y < height; y += 1) {
    let count = 0;
    let left = null;
    let right = null;
    for (let x = 0; x < width; x += 1) {
      if (isBackground(pixels, (y * width + x) * 4, background)) continue;
      count += 1;
      columnCounts[x] += 1;
      if (left === null) left = x;
      right = x;
    }
    contentPixels += count;
    rowSpans.push({ count, left, right });
  }
  return { rowSpans, columnCounts, contentPixels };
}

function decorativeBandDepth(counts, spanLength, dimensionLength) {
  const maximumDepth = Math.round(dimensionLength * decorativeBandMaximumDepthRatio);
  let depth = 0;
  for (const count of counts) {
    if (depth >= maximumDepth || count < spanLength * decorativeBandOccupancy) break;
    depth += 1;
  }
  return depth;
}

function interiorFrame(rowSpans, columnCounts, width, height) {
  const rowCounts = rowSpans.map((span) => span.count);
  const topTrim = decorativeBandDepth(rowCounts, width, height);
  const bottomTrim = decorativeBandDepth([...rowCounts].reverse(), width, height);
  const interiorHeight = height - topTrim - bottomTrim;
  const leftTrim = decorativeBandDepth(columnCounts, interiorHeight, width);
  const rightTrim = decorativeBandDepth([...columnCounts].reverse(), interiorHeight, width);
  return { top: topTrim, bottom: height - bottomTrim, left: leftTrim, right: width - rightTrim - 1 };
}

function rowIsOccupied(span, leftLimit, rightLimit) {
  return span.count > 0 && span.right >= leftLimit && span.left <= rightLimit;
}

function largestInternalGap(occupiedRows) {
  let largest = 0;
  for (let index = 1; index < occupiedRows.length; index += 1) largest = Math.max(largest, occupiedRows[index] - occupiedRows[index - 1] - 1);
  return largest;
}

function roundTo(value, digits) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

export function analyzePagePixels(pixels, width, height) {
  const background = cornerBackgroundColor(pixels, width, height);
  const { rowSpans, columnCounts, contentPixels } = contentRowSpans(pixels, width, height, background);
  const frame = interiorFrame(rowSpans, columnCounts, width, height);
  const occupiedRows = [];
  for (let y = frame.top; y < frame.bottom; y += 1) {
    if (rowIsOccupied(rowSpans[y], frame.left, frame.right)) occupiedRows.push(y);
  }
  const density = width * height ? roundTo(contentPixels / (width * height), 4) : 0;
  if (!occupiedRows.length) return { width, height, background, bounds: null, verticalGapRatio: 0, density };
  const bounds = {
    left: Math.max(frame.left, Math.min(...occupiedRows.map((y) => rowSpans[y].left))),
    top: occupiedRows[0],
    right: Math.min(frame.right, Math.max(...occupiedRows.map((y) => rowSpans[y].right))),
    bottom: occupiedRows[occupiedRows.length - 1],
  };
  return { width, height, background, bounds, verticalGapRatio: roundTo(largestInternalGap(occupiedRows) / height, 3), density };
}
