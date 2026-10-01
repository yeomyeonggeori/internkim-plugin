from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable
from xml.etree import ElementTree
import zipfile

from office_result import INPUT_NOT_FOUND, PDF_PASSWORD_REQUIRED, WRONG_INPUT_FORMAT, OfficeFailure



CONTENT_TYPES_PART = "[Content_Types].xml"
CONTENT_TYPES_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/content-types}"
PDF_SIGNATURE = b"%PDF-"
LEGACY_OFFICE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


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
OTHER_PACKAGE = InputKind("package", "a zip package that is not a Word, Excel or PowerPoint file", "")
OTHER = InputKind("other", "neither an Office file nor a PDF", "")
OPEN_XML_KINDS = (DOCX, XLSX, PPTX)
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
    if actual != expected:
        raise OfficeFailure(WRONG_INPUT_FORMAT.issue(f"{path} is {actual.description}, not {expected.description}", location=path, suggestion=redirect_suggestion(path, actual)))


def detected_kind(path: str) -> InputKind:
    with open(path, "rb") as input_file:
        head = input_file.read(8)
    if head.startswith(PDF_SIGNATURE):
        return PDF
    if head == LEGACY_OFFICE_SIGNATURE:
        return LEGACY_OFFICE
    if zipfile.is_zipfile(path):
        return open_xml_kind(path)
    return OTHER


def open_xml_kind(path: str) -> InputKind:
    content_types = main_content_types(path)
    return next((kind for kind in OPEN_XML_KINDS if kind.main_content_types & content_types), OTHER_PACKAGE)


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
    if actual.reader:
        return f"read it with office {actual.reader} {path}"
    return "check that the path names the file the user meant"


def require_unlocked_pdf(path: str, password: str | None) -> None:
    from pypdf import PdfReader

    reader = PdfReader(os.path.expanduser(path))
    if not reader.is_encrypted or reader.decrypt(password or ""):
        return
    if password is None:
        raise OfficeFailure(PDF_PASSWORD_REQUIRED.issue(f"{path} needs a password to open", location=path))
    raise OfficeFailure(PDF_PASSWORD_REQUIRED.issue(f"{path}: the password does not open it", location=path, suggestion="ask the user for the correct password"))
