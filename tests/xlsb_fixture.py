import struct
import zipfile

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.bin" ContentType="application/vnd.ms-excel.sheet.binary.macroEnabled.main"/>'
    '{sheets}'
    '<Override PartName="/xl/styles.bin" ContentType="application/vnd.ms-excel.styles"/>'
    '<Override PartName="/xl/sharedStrings.bin" ContentType="application/vnd.ms-excel.sharedStrings"/>'
    '</Types>'
)
PACKAGE_RELATIONSHIPS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.bin"/>'
    '</Relationships>'
)
RELATIONSHIP_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
DATE_STYLE = 1


def record(kind, payload=b""):
    return variable_length(kind, 2) + variable_length(len(payload), 4) + payload


def variable_length(value, limit):
    encoded = bytearray()
    for _ in range(limit):
        byte = value & 0x7F
        value >>= 7
        encoded.append(byte | (0x80 if value else 0))
        if not value:
            break
    return bytes(encoded)


def wide_text(text):
    return struct.pack("<I", len(text)) + text.encode("utf-16-le")


def workbook_part(names):
    sheets = b"".join(record(0x009C, struct.pack("<II", 0, index + 1) + wide_text(f"rId{index + 1}") + wide_text(name)) for index, name in enumerate(names))
    return record(0x0083) + record(0x0099, struct.pack("<II", 0, 0) + wide_text("")) + record(0x008F) + sheets + record(0x0090) + record(0x0084)


def styles_part():
    general = struct.pack("<HHHHHHHH", 0xFFFF, 0, 0, 0, 0, 0, 0, 0)
    short_date = struct.pack("<HHHHHHHH", 0, 14, 0, 0, 0, 0, 0, 0)
    return (
        record(0x0116)
        + record(0x0269, struct.pack("<I", 2)) + record(0x002F, general) + record(0x002F, short_date) + record(0x026A)
        + record(0x0117)
    )


def shared_strings_part(strings):
    items = b"".join(record(0x0013, b"\x00" + wide_text(text)) for text in strings)
    return record(0x009F, struct.pack("<II", len(strings), len(strings))) + items + record(0x00A0)


def cell_record(column, value, strings):
    if isinstance(value, tuple):
        return record(0x0005, struct.pack("<IId", column, DATE_STYLE, value[1]))
    if isinstance(value, bool):
        return record(0x0004, struct.pack("<IIB", column, 0, int(value)))
    if isinstance(value, (int, float)):
        return record(0x0005, struct.pack("<IId", column, 0, float(value)))
    return record(0x0007, struct.pack("<III", column, 0, strings.index(value)))


def sheet_part(rows, merges, strings):
    width = max(len(row) for row in rows)
    body = b""
    for row_index, row in enumerate(rows):
        body += record(0x0000, struct.pack("<IIHBBBI", row_index, 0, 300, 0, 0, 0, 0))
        body += b"".join(cell_record(column, value, strings) for column, value in enumerate(row) if value is not None)
    merged = b""
    if merges:
        merged = record(0x00B1, struct.pack("<I", len(merges))) + b"".join(record(0x00B0, struct.pack("<IIII", *merge)) for merge in merges) + record(0x00B2)
    return (
        record(0x0081)
        + record(0x0094, struct.pack("<IIII", 0, len(rows) - 1, 0, width - 1))
        + record(0x0091) + body + record(0x0092)
        + merged
        + record(0x0082)
    )


def write_xlsb(path, sheets):
    strings = sorted({value for _, rows, _ in sheets for row in rows for value in row if isinstance(value, str)})
    overrides = "".join(f'<Override PartName="/xl/worksheets/sheet{index + 1}.bin" ContentType="application/vnd.ms-excel.worksheet"/>' for index in range(len(sheets)))
    relationships = "".join(f'<Relationship Id="rId{index + 1}" Type="{RELATIONSHIP_TYPE}worksheet" Target="worksheets/sheet{index + 1}.bin"/>' for index in range(len(sheets)))
    relationships += f'<Relationship Id="rId{len(sheets) + 1}" Type="{RELATIONSHIP_TYPE}styles" Target="styles.bin"/>'
    relationships += f'<Relationship Id="rId{len(sheets) + 2}" Type="{RELATIONSHIP_TYPE}sharedStrings" Target="sharedStrings.bin"/>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES.format(sheets=overrides))
        archive.writestr("_rels/.rels", PACKAGE_RELATIONSHIPS)
        archive.writestr("xl/_rels/workbook.bin.rels", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{relationships}</Relationships>')
        archive.writestr("xl/workbook.bin", workbook_part([name for name, _, _ in sheets]))
        archive.writestr("xl/styles.bin", styles_part())
        archive.writestr("xl/sharedStrings.bin", shared_strings_part(strings))
        for index, (_, rows, merges) in enumerate(sheets):
            archive.writestr(f"xl/worksheets/sheet{index + 1}.bin", sheet_part(rows, merges, strings))
