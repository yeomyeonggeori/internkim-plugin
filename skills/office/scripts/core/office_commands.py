from __future__ import annotations

from dataclasses import dataclass
import re
import shlex


BATCH_MODES = ("all", "best-effort", "stop-on-error")
WHERE_KINDS = ("formula", "error", "number", "text", "empty")
EVERY_KIND = "*"
SETUP_COMMAND = "office setup"
OCR_SETUP_COMMAND = f"{SETUP_COMMAND} --with-ocr"
OCR_NEED = f"it needs the OCR engine that {OCR_SETUP_COMMAND} prepares, about 150 MB"
SHELL_SPECIAL = re.compile(r"[\s'\"\\$`;&|()*?!#~]")


@dataclass(frozen=True)
class Kind:
    name: str
    label: str
    extensions: tuple[str, ...]
    summary: str
    definitions_module: str


@dataclass(frozen=True)
class Flag:
    name: str
    meaning: str
    value: str = ""
    repeatable: bool = False
    number: type | None = None
    choices: tuple[str, ...] = ()
    default: object = None

    @property
    def takes_value(self) -> bool:
        return bool(self.value)

    @property
    def destination(self) -> str:
        return self.name.removeprefix("--").replace("-", "_")


@dataclass(frozen=True)
class Verb:
    name: str
    positionals: tuple[str, ...]
    summary: str
    subject: str | None
    definitions_module: str | None = None

    @property
    def usage(self) -> str:
        return " ".join([self.name, *(f"<{positional}>" for positional in self.positionals)])


@dataclass(frozen=True)
class Route:
    verb: str
    kind: str
    module: str
    summary: str
    flags: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    label: str = ""
    needs_packages: bool = True

    @property
    def name(self) -> str:
        return self.verb if self.kind == EVERY_KIND else f"{self.verb} {self.kind}"

    @property
    def reads_its_kind(self) -> bool:
        return not self.label


@dataclass(frozen=True)
class Conversion:
    source: str
    target: str
    note: str
    module: str = "convert.convert_file"
    needs_packages: bool = True


@dataclass(frozen=True)
class Tool:
    name: str
    usage: str
    summary: str


KINDS = (
    Kind("docx", ".docx", (".docx", ".docm", ".dotx", ".dotm"), "Word documents", "doc.doc_definitions"),
    Kind("xlsx", ".xlsx", (".xlsx", ".xlsm", ".xltx", ".xltm"), "Excel workbooks", "sheet.sheet_definitions"),
    Kind("pptx", ".pptx", (".pptx", ".pptm", ".potx", ".potm"), "PowerPoint decks, as delivered", "powerpoint.definitions"),
    Kind("pdf", ".pdf", (".pdf",), "PDF files", "pdf.pdf_definitions"),
    Kind("md", ".md", (".md", ".markdown"), "Markdown, the source a document is written in", "doc.doc_definitions"),
    Kind("csv", ".csv .tsv", (".csv", ".tsv"), "delimited rows", "sheet.sheet_definitions"),
    Kind("slides", "slides.html", (".html", ".htm"), "a deck written with the kit, or the folder holding it", "deck.deck_definitions"),
    Kind("form", "a form", (".json",), "company forms and contracts, named <jurisdiction>/<form> such as kr/quote", "paperwork.paperwork_definitions"),
)

FLAGS = (
    Flag("--output", "write the result to this copy and leave the file as it was", "PATH"),
    Flag("--dry-run", "check and plan every operation, report the changes, and write nothing"),
    Flag("--mode", "all (default) writes the batch whole or not at all; best-effort writes every operation that applies and reports the others; stop-on-error writes the operations before the first that does not apply", "MODE", choices=BATCH_MODES, default=BATCH_MODES[0]),
    Flag("--track", "write text, paragraph, row and block edits as tracked changes others can accept or reject"),
    Flag("--author", "author of tracked changes", "NAME"),
    Flag("--allow-loss", "save even when content the editor cannot carry, such as form controls, would be dropped"),
    Flag("--required-text", "a source fact that must appear; repeat for each fact", "TEXT", repeatable=True),
    Flag("--forbidden-text", "text that must not appear, such as an unsupported claim; repeat for each", "TEXT", repeatable=True),
    Flag("--slide-count", "the slide count the user asked for; a different count is an error", "N", number=int),
    Flag("--minimum-pages", "the fewest pages the file may have", "N", number=int),
    Flag("--maximum-pages", "the most pages the file may have", "N", number=int),
    Flag("--minimum-text-length", "the fewest characters of extractable text", "N", number=int),
    Flag("--required-font", "text that some embedded font's name must contain", "NAME"),
    Flag("--pages", "pages to use, such as 2,4-6; a deck's pages are its slides", "PAGES"),
    Flag("--start", "the first item to show: a block index from 0, or a page number from 1", "N", number=int),
    Flag("--limit", "the most items to show: blocks, pages or rows", "N", number=int),
    Flag("--sheet", "only this sheet", "NAME"),
    Flag("--range", "a range such as A1:F40; default the whole sheet", "RANGE"),
    Flag("--columns", "only these columns of the range, such as A,C:E", "COLUMNS"),
    Flag("--where", "list only the cells that hold a formula, an error, a number, text, or nothing", "KIND", choices=WHERE_KINDS),
    Flag("--stats", "per column: its header, value types, and count, min, max, sum and mean of the numbers"),
    Flag("--formats", "each formatted cell's number format, font, fill, border and alignment, with column widths and row heights"),
    Flag("--revisions", "list every tracked change with its id, type, author, date, block and text"),
    Flag("--styles", "also list every paragraph and table style name the document defines"),
    Flag("--detail", "add each paragraph's runs with where every style value comes from, fills, outlines, crops and animated shape ids"),
    Flag("--ocr", f"read pages that have no text layer from their image by OCR; {OCR_NEED}"),
    Flag("--with-ocr", "also prepare the OCR engine that read --ocr and convert --ocr use, about 150 MB"),
    Flag("--password", "the password that opens the PDF, when it has one", "PASSWORD"),
    Flag("--output-directory", "where the images go; default <name>-preview beside the file", "DIRECTORY"),
    Flag("--no-preview", "measure only, without drawing the pages"),
    Flag("--scale", "pixels per point; 1 is 72 dpi", "N", number=float),
    Flag("--font", "body font family of a .docx", "NAME"),
    Flag("--font-size", "body size in points of a .docx", "N", number=float),
    Flag("--font-path", "a font file to draw a .pdf with instead of the shipped one; a Bold file beside it is used for bold", "PATH"),
    Flag("--count", "how many candidates to save", "N", number=int),
)
FLAGS_BY_NAME = {flag.name: flag for flag in FLAGS}
BATCH_FLAGS = ("--output", "--dry-run", "--mode")
TEXT_FLAGS = ("--required-text", "--forbidden-text")

POSITIONALS = {
    "output": "the file to write; its extension names the format",
    "source": "what the new file is made from",
    "file": "the file",
    "operations": "a JSON file holding the list of operations",
    "template": "a .docx, .xlsx or .pptx with {{ placeholders }}, or a bundled form such as kr/quote",
    "values": "a JSON object holding each placeholder's value",
    "input": "the file to convert",
    "query": "a concrete English scene, such as \"harbor cranes at dawn\"; one or two words find more",
}

VERBS = (
    Verb("create", ("output", "source"), "make a new file; the source decides how", "source"),
    Verb("read", ("file",), "list what a file holds, with the indexes apply takes", "file"),
    Verb("apply", ("file", "operations"), "apply a batch of edits, whole or not at all unless --mode says otherwise", "file"),
    Verb("merge", ("template", "values", "output"), "fill a template's {{ placeholders }}, or a bundled form, from a values file", "template"),
    Verb("check", ("file",), "find what is wrong with a file before it is delivered", "file"),
    Verb("render", ("file",), "draw page images and a contact sheet to look at; never a deliverable", "file"),
    Verb("convert", ("input", "output"), "turn a file into another format; the two extensions pick the route", "input", "convert.convert_definitions"),
    Verb("image", ("query", "output"), "download up to three public-domain photos for an English search query", None, "deck.deck_definitions"),
)

ROUTES = (
    Route("create", "md", "doc.export_document", "a document written in Markdown, the usual way to make one", ("--font", "--font-size", "--font-path"), (".docx", ".pdf", ".html")),
    Route("create", "slides", "deck.build_deck", "a deck: checked first, then drawn, with a verdict and review images", ("--slide-count",) + TEXT_FLAGS, (".pdf", ".pptx", ".html")),
    Route("create", "docx", "doc.create_docx", "exact page setup, styles and blocks", outputs=(".docx",), label="JSON spec"),
    Route("create", "xlsx", "sheet.create_xlsx", "sheets of rows with formulas, formats, charts and pivots", outputs=(".xlsx",), label="JSON spec"),
    Route("create", "pdf", "pdf.create_pdf", "sections and tables placed on the page", outputs=(".pdf",), label="JSON spec"),
    Route("create", "csv", "convert.import_table", "typed cells under a frozen, filtered header", outputs=(".xlsx", ".pdf")),
    Route("read", "docx", "doc.read_docx", "blocks, headers, footers, comments, charts and tracked changes by index", ("--start", "--limit", "--revisions", "--styles")),
    Route("read", "xlsx", "sheet.read_xlsx", "sheets, charts and features; a range's values, formulas, stats or formats", ("--sheet", "--range", "--columns", "--limit", "--where", "--stats", "--formats")),
    Route("read", "pptx", "powerpoint.read_pptx", "each slide's shapes with index, box, text and style, tables, charts and notes", ("--pages", "--detail")),
    Route("read", "pdf", "pdf.read_pdf", "text and tables by page, page sizes, and which pages are scans", ("--start", "--limit", "--ocr", "--password")),
    Route("apply", "docx", "doc.apply_docx", "text, blocks, tables, pictures, styles, sections, comments and tracked changes", BATCH_FLAGS + ("--track", "--author")),
    Route("apply", "xlsx", "sheet.apply_xlsx", "cells, formulas, formats, rules, rows, sheets, charts and pivots", BATCH_FLAGS + ("--allow-loss",)),
    Route("apply", "pptx", "powerpoint.apply_pptx", "text, shapes, tables, charts and slides, reporting the layout problems left", BATCH_FLAGS),
    Route("apply", "pdf", "pdf.apply_pdf", "section pages appended at the end", BATCH_FLAGS + ("--password",)),
    Route("merge", "docx", "doc.merge_docx", "a filled .docx; a paragraph or row naming a list repeats per item"),
    Route("merge", "xlsx", "sheet.merge_xlsx", "a filled .xlsx; a cell that is one placeholder takes the value's type"),
    Route("merge", "pptx", "powerpoint.merge_pptx", "a filled .pptx"),
    Route("merge", "form", "paperwork.merge_form", "a form on letterhead to .pdf, or a contract to .docx", outputs=(".pdf", ".docx"), label="<jurisdiction>/<form>"),
    Route("check", "docx", "doc.check_docx", "placeholders, references, contents list, fonts, pictures, comments, layout, required text", TEXT_FLAGS),
    Route("check", "xlsx", "sheet.check_xlsx", "formula errors, broken names, numbers stored as text, wide numbers, frozen headers, filters and required text", TEXT_FLAGS),
    Route("check", "pdf", "pdf.check_pdf", "pages, extractable text, embedded fonts and required text", TEXT_FLAGS + ("--minimum-pages", "--maximum-pages", "--minimum-text-length", "--required-font", "--password")),
    Route("check", "pptx", "powerpoint.check_pptx", "text overflowing, shapes off the slide and overlaps, slide count and required text, with slide images", ("--slide-count",) + TEXT_FLAGS + ("--pages", "--output-directory", "--no-preview")),
    Route("check", "slides", "deck.check_deck", "layout, chart, image, placeholder, slide-count, palette and required-text defects, without drawing", ("--slide-count",) + TEXT_FLAGS),
    Route("check", "form", "paperwork.check_amounts", "a form's row amounts, totals, tax and amount in words, never rewriting it", label="form values", needs_packages=False),
    Route("render", "docx", "doc.render_docx", "pages as Word lays them out, with a PDF", ("--output-directory",)),
    Route("render", "xlsx", "sheet.render_xlsx", "each sheet as printed pages, with a PDF", ("--sheet", "--output-directory")),
    Route("render", "pdf", "pdf.render_pdf", "the pages as they are", ("--pages", "--scale", "--output-directory", "--password")),
    Route("render", "pptx", "powerpoint.render_pptx", "the slides as PowerPoint draws them", ("--pages", "--output-directory")),
    Route("convert", EVERY_KIND, "convert.convert_file", "", ("--sheet", "--ocr", "--password")),
    Route("image", EVERY_KIND, "deck.fetch_image", "saved as <output>, then <output stem>-2 and -3, each with its licence and source", ("--count",)),
)

CONVERSIONS = (
    Conversion("docx", "pdf", "each page as render lays it out: page size, margins, styles, tables, pictures, headers and footers"),
    Conversion("docx", "md", "final text with tracked changes accepted; images saved beside the output; comments, notes, fields and layout dropped"),
    Conversion("docx", "html", "one self-contained page; the same content as docx to md"),
    Conversion("xlsx", "pdf", "each visible sheet as render prints it: print area, scaling, number formats, fills, borders and charts"),
    Conversion("xlsx", "csv", "cached values; one file per sheet unless --sheet picks one; UTF-8 with BOM so Excel reads Korean"),
    Conversion("xlsx", "tsv", "the same as xlsx to csv, tab-separated"),
    Conversion("pptx", "pdf", "each slide as render draws it: shapes, text, pictures, tables and charts"),
    Conversion("pdf", "docx", "text PDFs only: paragraphs, headings by font size, lists, tables drawn with lines or laid out in aligned columns, images and two-column reading order; page layout is reflowed"),
    Conversion("pdf", "md", "the same content as pdf to docx"),
    Conversion("pdf", "xlsx", "each table, drawn with lines or laid out in aligned columns, as a sheet; a table whose header repeats on the next page continues; numbers, percents and dates typed; text outside tables is left out"),
    Conversion("pdf", "pptx", "one slide per page at the page's size: text lines as text boxes, tables as tables, images as pictures; a page with drawn shapes or no text becomes one picture with its text in the notes"),
    Conversion("html", "docx", "headings, paragraphs, lists, tables, bold, italic, links and images"),
    Conversion("html", "md", "the same content as html to docx"),
    Conversion("html", "pdf", "the same content as html to docx, laid out as a document; the page's own CSS and scripts are not applied"),
    Conversion("html", "html", "a delivered deck .html back to the small slides.html it was built from: the kit, viewer and vendored fonts removed, inlined images and fonts pointing at their files again", "deck.restore_source", needs_packages=False),
    Conversion("xls", "xlsx", "values, dates and merged cells; formulas kept as their values; fonts, colors, borders and widths dropped"),
    Conversion("ods", "xlsx", "the same as xls to xlsx"),
    Conversion("xlsb", "xlsx", "the same as xls to xlsx; formulas kept as their saved values"),
)
EXTENSION_ALIASES = {"markdown": "md", "htm": "html", "xlsm": "xlsx"}

TOOLS = (
    Tool("guide", "guide [verb] [kind] [operation]", "print what a verb or kind takes: fields, operations, rules and issue codes"),
    Tool("setup", "setup [--with-ocr]", "install the Python environment and the renderer into the skill, and with --with-ocr the OCR engine; nothing else installs anything"),
    Tool("python", "python <script.py> [arguments]", "run a task-local Python script with the office packages"),
)


def command_text(words: list[str]) -> str:
    return " ".join(shlex.quote(word) if not word or SHELL_SPECIAL.search(word) else word for word in words)


def find_verb(name: str) -> Verb | None:
    return next((verb for verb in VERBS if verb.name == name), None)


def find_kind(name: str) -> Kind | None:
    return next((kind for kind in KINDS if kind.name == name), None)


def find_route(verb_name: str, kind_name: str) -> Route | None:
    return next((route for route in ROUTES if route.verb == verb_name and route.kind in (kind_name, EVERY_KIND)), None)


def verb_routes(verb_name: str) -> list[Route]:
    return [route for route in ROUTES if route.verb == verb_name]


def kind_routes(kind_name: str) -> list[Route]:
    return [route for route in ROUTES if route.kind == kind_name]


def route_label(route: Route) -> str:
    if route.label:
        return route.label
    kind = find_kind(route.kind)
    return kind.label if kind else route.verb


def normalized_extension(extension: str) -> str:
    lowered = extension.lower().lstrip(".")
    return EXTENSION_ALIASES.get(lowered, lowered)


def find_conversion(source: str, target: str) -> Conversion | None:
    return next((conversion for conversion in CONVERSIONS if (conversion.source, conversion.target) == (source, target)), None)


def conversion_sources() -> list[str]:
    return list(dict.fromkeys(conversion.source for conversion in CONVERSIONS))


def conversion_targets(source: str) -> list[str]:
    return [conversion.target for conversion in CONVERSIONS if conversion.source == source]


def definitions_modules() -> list[str]:
    modules = [kind.definitions_module for kind in KINDS] + [verb.definitions_module for verb in VERBS if verb.definitions_module]
    return list(dict.fromkeys(modules))
