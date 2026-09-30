import pathlib
import struct
import typing
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BYTES_PER_PIXEL_BY_COLOR_TYPE = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
Pixel = tuple[int, int, int, int]
PixelRows = list[list[Pixel]]


def read_png(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(str(path) + " is not a PNG")
    width = height = bit_depth = color_type = 0
    palette = []
    compressed_parts = []
    for chunk_type, chunk_data in png_chunks(data):
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = parse_ihdr(chunk_data)
        elif chunk_type == b"PLTE":
            palette = parse_palette(chunk_data)
        elif chunk_type == b"IDAT":
            compressed_parts.append(chunk_data)
    if bit_depth != 8:
        raise ValueError(str(path) + " uses unsupported PNG bit depth")
    rows = decode_png_rows(width, height, color_type, palette, b"".join(compressed_parts))
    return {"width": width, "height": height, "rows": rows}


def png_chunks(data: bytes) -> typing.Iterator[tuple[bytes, bytes]]:
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        if chunk_type == b"IEND":
            return
        yield chunk_type, data[offset + 8:offset + 8 + length]
        offset += 12 + length


def parse_ihdr(chunk_data: bytes) -> Pixel:
    width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk_data)
    return width, height, bit_depth, color_type


def parse_palette(chunk_data: bytes) -> list[Pixel]:
    return [(chunk_data[index], chunk_data[index + 1], chunk_data[index + 2], 255) for index in range(0, len(chunk_data), 3)]


def decode_png_rows(
    width: int,
    height: int,
    color_type: int,
    palette: list[Pixel],
    compressed_data: bytes,
) -> PixelRows:
    decompressed_data = zlib.decompress(compressed_data)
    bytes_per_pixel = png_bytes_per_pixel(color_type)
    stride = width * bytes_per_pixel
    rows = []
    previous = [0] * stride
    offset = 0
    for _ in range(height):
        filter_type = decompressed_data[offset]
        offset += 1
        current = list(decompressed_data[offset:offset + stride])
        offset += stride
        reconstructed = unfilter_row(filter_type, current, previous, bytes_per_pixel)
        rows.append(pixels_from_row(reconstructed, color_type, palette))
        previous = reconstructed
    return rows


def png_bytes_per_pixel(color_type: int) -> int:
    if color_type not in BYTES_PER_PIXEL_BY_COLOR_TYPE:
        raise ValueError("unsupported PNG color type")
    return BYTES_PER_PIXEL_BY_COLOR_TYPE[color_type]


def unfilter_row(filter_type: int, current: list[int], previous: list[int], bytes_per_pixel: int) -> list[int]:
    row = current[:]
    for index, value in enumerate(row):
        left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index] if index < len(previous) else 0
        upper_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel and index < len(previous) else 0
        if filter_type == 1:
            row[index] = (value + left) & 255
        elif filter_type == 2:
            row[index] = (value + up) & 255
        elif filter_type == 3:
            row[index] = (value + ((left + up) // 2)) & 255
        elif filter_type == 4:
            row[index] = (value + paeth_predictor(left, up, upper_left)) & 255
        elif filter_type != 0:
            raise ValueError("unsupported PNG filter")
    return row


def paeth_predictor(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def pixels_from_row(row: list[int], color_type: int, palette: list[Pixel]) -> list[Pixel]:
    pixels = []
    step = png_bytes_per_pixel(color_type)
    for index in range(0, len(row), step):
        if color_type == 0:
            value = row[index]
            pixels.append((value, value, value, 255))
        elif color_type == 2:
            pixels.append((row[index], row[index + 1], row[index + 2], 255))
        elif color_type == 3:
            pixels.append(palette[row[index]])
        elif color_type == 4:
            value = row[index]
            pixels.append((value, value, value, row[index + 1]))
        elif color_type == 6:
            pixels.append((row[index], row[index + 1], row[index + 2], row[index + 3]))
    return pixels


def write_png(path: pathlib.Path, width: int, height: int, rows: PixelRows) -> None:
    raw_rows = []
    for row in rows:
        raw_row = bytearray([0])
        for red, green, blue, alpha in row:
            raw_row.extend([red, green, blue, alpha])
        raw_rows.append(bytes(raw_row))
    chunks = [
        png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
        png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows))),
        png_chunk(b"IEND", b""),
    ]
    path.write_bytes(PNG_SIGNATURE + b"".join(chunks))


def png_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
    return struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", checksum)
