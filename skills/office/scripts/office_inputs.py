from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import io
import os
from typing import Callable
from xml.etree import ElementTree
import zipfile
import zlib

from office_result import FILE_DAMAGED, INPUT_NOT_FOUND, PDF_PASSWORD_REQUIRED, WRONG_INPUT_FORMAT, OfficeFailure



CONTENT_TYPES_PART = "[Content_Types].xml"
PACKAGE_RELATIONSHIPS_PART = "_rels/.rels"
MAIN_PART_RELATIONSHIPS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
)
TEXT_ENCODINGS = ("utf-8-sig", "cp949")
CONTENT_TYPES_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/content-types}"
PDF_SIGNATURE = b"%PDF-"
LEGACY_OFFICE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_SIGNATURE = b"PK\x03\x04"


@dataclass(frozen=True)
class InputKind:
    name: str
    description: str
    reader: str
    main_content_types: frozenset[str] = frozenset()


DOCX = InputKind("docx", "a Word document", "doc read", frozenset({
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml",
    "application/vnd.ms-word.document.macroEnabled.main+xml",
    "application/vnd.ms-word.template.macroEnabledTemplate.main+xml",
}))
XLSX = InputKind("xlsx", "an Excel workbook", "sheet read", frozenset({
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.template.main+xml",
    "application/vnd.ms-excel.sheet.macroEnabled.main+xml",
    "application/vnd.ms-excel.template.macroEnabled.main+xml",
}))
PPTX = InputKind("pptx", "a PowerPoint deck", "deck read", frozenset({
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml",
    "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml",
    "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml",
}))
PDF = InputKind("pdf", "a PDF", "pdf read")
LEGACY_OFFICE = InputKind("legacy", "a pre-2007 Office file (.doc, .xls or .ppt)", "office convert")
XLSB = InputKind("xlsb", "a binary Excel workbook (.xlsb)", "office convert", frozenset({
    "application/vnd.ms-excel.sheet.binary.macroEnabled.main",
}))
OTHER_PACKAGE = InputKind("package", "a zip package that is not a Word, Excel or PowerPoint file", "")
DAMAGED_PACKAGE = InputKind("damaged-package", "a zip package cut short or damaged", "")
OTHER = InputKind("other", "neither an Office file nor a PDF", "")
OPEN_XML_KINDS = (DOCX, XLSX, PPTX, XLSB)
MACRO_ENABLED_CONTENT_TYPES = frozenset(content_type for kind in OPEN_XML_KINDS for content_type in kind.main_content_types if "macroEnabled" in content_type)
KINDS_BY_NAME = {kind.name: kind for kind in (DOCX, XLSX, PPTX, PDF)}


def office_file(kind_name: str) -> Callable[[str], str]:
    expected = KINDS_BY_NAME[kind_name]

    def checked_path(path: str) -> str:
        require_kind(path, expected)
        return path

    return checked_path


def add_password_argument(parser) -> None:
    parser.add_argument("--password", help="the password that opens the PDF, when it has one")


def require_kind(path: str, expected: InputKind) -> None:
    expanded_path = os.path.expanduser(path)
    if not os.path.isfile(expanded_path):
        raise OfficeFailure(INPUT_NOT_FOUND.issue(f"{path}: no such file", location=path))
    actual = detected_kind(expanded_path)
    if actual == DAMAGED_PACKAGE:
        raise OfficeFailure(FILE_DAMAGED.issue(f"{path} is {actual.description}; it cannot be read as {expected.description}", location=path))
    if actual != expected:
        raise OfficeFailure(WRONG_INPUT_FORMAT.issue(f"{path} is {actual.description}, not {expected.description}", location=path, suggestion=redirect_suggestion(path, actual)))
    problem = package_problem(expanded_path) if expected in OPEN_XML_KINDS else None
    if problem is not None:
        raise OfficeFailure(FILE_DAMAGED.issue(f"{path} cannot be read as {expected.description}: {problem}", location=path))


def package_problem(path: str) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if PACKAGE_RELATIONSHIPS_PART not in names:
                return "it has no package relationships"
            main_part = main_part_name(ElementTree.fromstring(archive.read(PACKAGE_RELATIONSHIPS_PART)))
            if main_part not in names:
                return "its main part is missing"
            with archive.open(main_part) as part:
                ElementTree.parse(part)
    except (zipfile.BadZipFile, ElementTree.ParseError, EOFError, zlib.error) as error:
        return str(error) or type(error).__name__
    return None


def main_part_name(relationships) -> str:
    targets = [relationship.get("Target", "") for relationship in relationships if relationship.get("Type") in MAIN_PART_RELATIONSHIPS]
    return targets[0].lstrip("/") if targets else ""


def read_text_input(path: str) -> str:
    expanded_path = os.path.expanduser(path)
    with open(expanded_path, "rb") as input_file:
        data = input_file.read()
    kind = detected_kind(expanded_path)
    if kind != OTHER:
        raise OfficeFailure(WRONG_INPUT_FORMAT.issue(f"{path} is {kind.description}, not a text file", location=path, suggestion=redirect_suggestion(path, kind)))
    for encoding in TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise OfficeFailure(WRONG_INPUT_FORMAT.issue(f"{path} is neither UTF-8 nor CP949 text", location=path, suggestion="save the file as UTF-8 text and rerun"))


def detected_kind(path: str) -> InputKind:
    with open(path, "rb") as input_file:
        head = input_file.read(8)
    if head.startswith(PDF_SIGNATURE):
        return PDF
    if head == LEGACY_OFFICE_SIGNATURE:
        return LEGACY_OFFICE
    if zipfile.is_zipfile(path):
        return open_xml_kind(path)
    if head.startswith(ZIP_SIGNATURE):
        return DAMAGED_PACKAGE
    return OTHER


def open_xml_kind(path: str) -> InputKind:
    content_types = main_content_types(path)
    return next((kind for kind in OPEN_XML_KINDS if kind.main_content_types & content_types), OTHER_PACKAGE)


def holds_macros(path: str) -> bool:
    return bool(main_content_types(os.path.expanduser(path)) & MACRO_ENABLED_CONTENT_TYPES)


def package_stream(path: str) -> io.BytesIO:
    with open(os.path.expanduser(path), "rb") as input_file:
        return io.BytesIO(input_file.read())


def main_content_types(path: str) -> set[str]:
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read(CONTENT_TYPES_PART))
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return set()
    return {element.get("ContentType", "") for element in root.iter(f"{CONTENT_TYPES_NAMESPACE}Override")}


def redirect_suggestion(path: str, actual: InputKind) -> str:
    if actual == LEGACY_OFFICE:
        return f"convert it first: office convert {path} <name>.docx, .xlsx or .pptx"
    if actual == XLSB:
        return f"convert it first: office convert {path} <name>.xlsx"
    if actual.reader:
        return f"read it with office {actual.reader} {path}"
    return "check that the path names the file the user meant"


def require_unlocked_pdf(path: str, password: str | None) -> None:
    from pypdf import PdfReader

    with damaged_pdf_refused(path):
        reader = PdfReader(os.path.expanduser(path))
        require_password_opens(reader, path, password)
        len(reader.pages)


def require_password_opens(reader, path: str, password: str | None) -> None:
    if not reader.is_encrypted or reader.decrypt(password or ""):
        return
    if password is None:
        raise OfficeFailure(PDF_PASSWORD_REQUIRED.issue(f"{path} needs a password to open", location=path))
    raise OfficeFailure(PDF_PASSWORD_REQUIRED.issue(f"{path}: the password does not open it", location=path, suggestion="ask the user for the correct password"))


@contextmanager
def damaged_pdf_refused(path: str):
    from pypdf.errors import PyPdfError

    try:
        yield
    except PyPdfError as error:
        raise OfficeFailure(FILE_DAMAGED.issue(f"{path} cannot be read as a PDF: {error}", location=path)) from error


def unlocked_pdf_bytes(path: str, password: str | None) -> bytes:
    from pypdf import PdfReader, PdfWriter

    expanded_path = os.path.expanduser(path)
    reader = PdfReader(expanded_path)
    if not reader.is_encrypted:
        with open(expanded_path, "rb") as input_file:
            return input_file.read()
    # pdfminer.six 20260107 pdftypes.uint_value turns an /Encrypt /P of 0 into 2**32, which its RC4 key derivation cannot pack
    reader.decrypt(password or "")
    stream = io.BytesIO()
    PdfWriter(clone_from=reader).write(stream)
    return stream.getvalue()
