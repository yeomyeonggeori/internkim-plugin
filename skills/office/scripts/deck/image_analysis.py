from __future__ import annotations

from png_codec import Pixel


DECORATIVE_BAND_OCCUPANCY = 0.85
DECORATIVE_BAND_MAXIMUM_DEPTH_RATIO = 0.15
BACKGROUND_COLOR_DISTANCE_LIMIT = 34


def corner_background_color(image: dict[str, object]) -> Pixel:
    rows = image["rows"]
    width = image["width"]
    height = image["height"]
    samples = []
    sample_size = max(6, min(width, height) // 40)
    for y in list(range(sample_size)) + list(range(height - sample_size, height)):
        for x in list(range(sample_size)) + list(range(width - sample_size, width)):
            samples.append(rows[y][x])
    return median_color(samples)


def median_color(samples: list[Pixel]) -> Pixel:
    channels = []
    for channel_index in range(4):
        values = sorted(sample[channel_index] for sample in samples)
        channels.append(values[len(values) // 2])
    return tuple(channels)


def analyze_image_content(image: dict[str, object], background: Pixel) -> dict[str, object]:
    row_spans, column_counts = content_row_spans(image, background)
    frame = interior_frame(row_spans, column_counts, image["width"], image["height"])
    occupied_rows = [
        y
        for y in range(frame["top"], frame["bottom"])
        if row_is_occupied(row_spans[y], frame["left"], frame["right"])
    ]
    if not occupied_rows:
        return {"bounds": None, "verticalGapRatio": 0.0}
    bounds = {
        "left": max(frame["left"], min(row_spans[y]["left"] for y in occupied_rows)),
        "top": occupied_rows[0],
        "right": min(frame["right"], max(row_spans[y]["right"] for y in occupied_rows)),
        "bottom": occupied_rows[-1],
    }
    largest_gap = largest_internal_gap(occupied_rows)
    return {"bounds": bounds, "verticalGapRatio": round(largest_gap / image["height"], 3)}


def interior_frame(row_spans: list[dict[str, object]], column_counts: list[int], width: int, height: int) -> dict[str, int]:
    row_counts = [span["count"] for span in row_spans]
    top_trim = decorative_band_depth(row_counts, width, height)
    bottom_trim = decorative_band_depth(list(reversed(row_counts)), width, height)
    interior_height = height - top_trim - bottom_trim
    left_trim = decorative_band_depth(column_counts, interior_height, width)
    right_trim = decorative_band_depth(list(reversed(column_counts)), interior_height, width)
    return {"top": top_trim, "bottom": height - bottom_trim, "left": left_trim, "right": width - right_trim - 1}


def content_row_spans(
    image: dict[str, object], background: Pixel
) -> tuple[list[dict[str, object]], list[int]]:
    width = image["width"]
    column_counts = [0] * width
    row_spans = []
    for row in image["rows"]:
        count = 0
        left = None
        right = None
        for x, pixel in enumerate(row):
            if is_background_pixel(pixel, background):
                continue
            count += 1
            column_counts[x] += 1
            if left is None:
                left = x
            right = x
        row_spans.append({"count": count, "left": left, "right": right})
    return row_spans, column_counts


def decorative_band_depth(counts: list[int], span_length: int, dimension_length: int) -> int:
    maximum_depth = round(dimension_length * DECORATIVE_BAND_MAXIMUM_DEPTH_RATIO)
    depth = 0
    for count in counts:
        if depth >= maximum_depth or count < span_length * DECORATIVE_BAND_OCCUPANCY:
            break
        depth += 1
    return depth


def row_is_occupied(span: dict[str, object], left_limit: int, right_limit: int) -> bool:
    if span["count"] == 0:
        return False
    return int(span["right"]) >= left_limit and int(span["left"]) <= right_limit


def largest_internal_gap(occupied_rows: list[int]) -> int:
    largest = 0
    for previous_row, next_row in zip(occupied_rows, occupied_rows[1:]):
        largest = max(largest, next_row - previous_row - 1)
    return largest


def content_density(image: dict[str, object], background: Pixel) -> float:
    total_pixels = image["width"] * image["height"]
    if total_pixels == 0:
        return 0
    content_pixels = sum(1 for row in image["rows"] for pixel in row if not is_background_pixel(pixel, background))
    return round(content_pixels / total_pixels, 4)


def is_background_pixel(pixel: Pixel, background: Pixel) -> bool:
    if pixel[3] < 8:
        return True
    distance = sum(abs(pixel[index] - background[index]) for index in range(3))
    return distance <= BACKGROUND_COLOR_DISTANCE_LIMIT
