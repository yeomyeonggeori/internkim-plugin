from __future__ import annotations

from dataclasses import dataclass
import pathlib
import struct


WINDOWS_PLATFORM = 3
UNICODE_BMP_ENCODING = 1
ENGLISH_UNITED_STATES = 0x409
FAMILY_NAME_ID = 1
SUBFAMILY_NAME_ID = 2
FULL_NAME_ID = 4
VERSION_NAME_ID = 5
EOT_VERSION = 0x00020002
EOT_MAGIC_NUMBER = 0x504C
EOT_ROOT_STRING_CHECKSUM = 0x50475342
EOT_EUDC_CODE_PAGE = 0x000004E4
KOREAN_CODE_PAGE_BITS = (19, 21)
HANGUL_CHARSET = 129


@dataclass(frozen=True)
class TrueTypeFace:
    data: bytes
    family: str
    subfamily: str
    full_name: str
    version: str
    weight: int
    italic: bool
    fs_type: int
    panose: bytes
    unicode_ranges: tuple[int, int, int, int]
    code_page_ranges: tuple[int, int]
    checksum_adjustment: int

    @property
    def charset(self) -> int:
        if any(self.code_page_ranges[0] & (1 << bit) for bit in KOREAN_CODE_PAGE_BITS):
            return HANGUL_CHARSET
        return 0

    @property
    def signed_charset(self) -> int:
        return self.charset - 256 if self.charset > 127 else self.charset

    @property
    def allows_embedding(self) -> bool:
        return self.fs_type & 0x000F != 0x0002


def read_truetype_face(path: pathlib.Path) -> TrueTypeFace:
    data = path.read_bytes()
    tables = table_directory(data)
    names = english_names(data, tables[b"name"])
    os2_offset = tables[b"OS/2"][0]
    head_offset = tables[b"head"][0]
    os2_version = struct.unpack_from(">H", data, os2_offset)[0]
    return TrueTypeFace(
        data=data,
        family=names[FAMILY_NAME_ID],
        subfamily=names.get(SUBFAMILY_NAME_ID, ""),
        full_name=names.get(FULL_NAME_ID, names[FAMILY_NAME_ID]),
        version=names.get(VERSION_NAME_ID, ""),
        weight=struct.unpack_from(">H", data, os2_offset + 4)[0],
        italic=bool(struct.unpack_from(">H", data, os2_offset + 62)[0] & 0x01),
        fs_type=struct.unpack_from(">H", data, os2_offset + 8)[0],
        panose=data[os2_offset + 32:os2_offset + 42],
        unicode_ranges=struct.unpack_from(">4I", data, os2_offset + 42),
        code_page_ranges=struct.unpack_from(">2I", data, os2_offset + 78) if os2_version >= 1 else (0, 0),
        checksum_adjustment=struct.unpack_from(">I", data, head_offset + 8)[0],
    )


def table_directory(data: bytes) -> dict[bytes, tuple[int, int]]:
    table_count = struct.unpack_from(">H", data, 4)[0]
    tables = {}
    for index in range(table_count):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + index * 16)
        tables[tag] = (offset, length)
    return tables


def english_names(data: bytes, name_table: tuple[int, int]) -> dict[int, str]:
    table_offset = name_table[0]
    _, record_count, strings_offset = struct.unpack_from(">HHH", data, table_offset)
    names = {}
    for index in range(record_count):
        platform, encoding, language, name_id, length, offset = struct.unpack_from(">6H", data, table_offset + 6 + index * 12)
        if (platform, encoding, language) != (WINDOWS_PLATFORM, UNICODE_BMP_ENCODING, ENGLISH_UNITED_STATES):
            continue
        start = table_offset + strings_offset + offset
        names[name_id] = data[start:start + length].decode("utf-16-be")
    return names


def embedded_open_type(face: TrueTypeFace) -> bytes:
    header = b"".join((
        struct.pack("<III", len(face.data), EOT_VERSION, 0),
        face.panose,
        struct.pack("<BBIHH", 0, int(face.italic), face.weight, face.fs_type, EOT_MAGIC_NUMBER),
        struct.pack("<4I", *face.unicode_ranges),
        struct.pack("<2I", *face.code_page_ranges),
        struct.pack("<I", face.checksum_adjustment),
        bytes(16),
        eot_name(face.family),
        eot_name(face.subfamily),
        eot_name(face.version),
        eot_name(face.full_name),
        struct.pack("<HH", 0, 0),
        struct.pack("<II", EOT_ROOT_STRING_CHECKSUM, EOT_EUDC_CODE_PAGE),
        struct.pack("<HHII", 0, 0, 0, 0),
    ))
    total_size = 4 + len(header) + len(face.data)
    return struct.pack("<I", total_size) + header + face.data


def eot_name(text: str) -> bytes:
    encoded = text.encode("utf-16-le") + b"\x00\x00"
    return struct.pack("<HH", 0, len(encoded)) + encoded
