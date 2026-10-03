from __future__ import annotations

from core.office_result import ERROR, WARNING, IssueKind
from core.office_schema import AnyOf, Boolean, CellValue, Field, ListOf, Number, Record, Text, Variant
from paperwork.paperwork_design import FONT_KOREAN_DOCX
from fonts.font_files import FONT_PATH_MEANING
from paperwork.template_context import caller_fields, default_values, derived_values, list_fields, optional_paragraph_fields
from paperwork.template_fields import template_names
from paperwork.forms import Form, form_slugs
from paperwork.jurisdictions import JURISDICTIONS, Jurisdiction
from doc.doc_definitions import GLYPH_NOT_COVERED
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE


LABELED_VALUE = Record("labeled value", "one label and its value", (
    Field("label", CellValue(), "the label"),
    Field("value", CellValue(), "the value"),
))

PROFILE = Record("profile", "the company_info_get result, pasted whole; the letterhead reads these fields", (
    Field("name", CellValue(), "company name; name or companyName is required"),
    Field("companyName", CellValue(), "company name when name is absent"),
    Field("logoPath", CellValue(), "logo image at the letterhead's left"),
    Field("legalAttributes", ListOf(LABELED_VALUE), "the first two print on the letterhead, such as the business registration number"),
    Field("registrationNumber", CellValue(), "printed after the jurisdiction's registration label when legalAttributes is empty"),
    Field("representative", CellValue(), "representative's name"),
    Field("representativeTitle", CellValue(), "title before the name, default the jurisdiction's representative title"),
    Field("address", CellValue(), "address line"),
    Field("phone", CellValue(), "contact line"),
    Field("email", CellValue(), "contact line"),
    Field("website", CellValue(), "contact line"),
    Field("stampPath", CellValue(), "seal image placed on the signature when signature.stamp is true"),
), keeps_other_fields=True)

ITEMS = Record("items", "the item table with its totals", (
    Field("headers", ListOf(CellValue(), non_empty=True), "column headers", required=True),
    Field("rows", ListOf(ListOf(CellValue())), "item rows"),
    Field("aligns", ListOf(CellValue()), "L, C or R per column; anything else aligns left"),
    Field("untaxedRows", ListOf(Number(minimum=0, integer=True)), "indexes, from 0, of the rows that carry no tax, such as exempt or zero-rated supplies; their tax cell holds 0 and the tax total leaves their amounts out"),
    Field("totals", ListOf(LABELED_VALUE), "right-aligned total lines, the last one emphasized"),
))

RECIPIENT = Record("recipient", "the addressee block", (
    Field("label", CellValue(), "caption above the lines, default the jurisdiction's recipient label"),
    Field("lines", ListOf(CellValue()), "addressee lines"),
))

PAPERWORK_SECTION = Record("section", "a titled block of paragraphs and bullets", (
    Field("title", CellValue(), "section title"),
    Field("paragraphs", ListOf(CellValue()), "paragraphs"),
    Field("bullets", ListOf(CellValue()), "bullet items"),
))

SIGNATURE = Record("signature", "the dated signature line", (
    Field("date", CellValue(), "date line"),
    Field("line", CellValue(), "signer line; the jurisdiction's seal mark, where it has one, is appended"),
    Field("stamp", Boolean(), "place profile.stampPath on the signer line"),
))

FORM_FIELD = Field("form", Text(non_empty=True), "the form these values fill, <jurisdiction>/<form> such as kr/quote; office merge takes it from its first argument and office check from here")

PAPERWORK_DOCUMENT = Record("document", "the values office merge draws on letterhead as a .pdf; each spec under references/paperwork has its skeleton", (
    FORM_FIELD,
    Field("title", Text(non_empty=True), "centered document title", required=True),
    Field("documentNumber", CellValue(), "printed under the title after the jurisdiction's document-number label"),
    Field("profile", PROFILE, "company profile for the letterhead", required=True),
    Field("approvalLine", ListOf(Text()), "approval box captions, left to right"),
    Field("recipient", RECIPIENT, "addressee"),
    Field("meta", ListOf(LABELED_VALUE), "label-value table under the title"),
    Field("items", ITEMS, "item table"),
    Field("sections", ListOf(PAPERWORK_SECTION), "body sections"),
    Field("notes", AnyOf((Text(), ListOf(CellValue()))), "centered closing lines"),
    Field("signature", AnyOf((Text(), SIGNATURE)), "signature; text becomes date on its first line and signer after"),
    Field("footer", CellValue(), "footer line on every page"),
    Field("taxRatePercent", Number(minimum=0), "the tax rate the form states, which office check uses where the jurisdiction sets none"),
    Field("fontPath", Text(), FONT_PATH_MEANING),
))

PAPERWORK_CONTENT_FIELDS = ("recipient", "meta", "items", "sections", "notes", "signature")

CONTRACT_BLOCK = Variant(
    "contract block",
    "one piece of a .docx contract, in reading order",
    "type",
    (
        Record("heading", "a bold clause heading; every level renders alike", (
            Field("text", CellValue(), "heading text"),
            Field("level", Number(1, 4, integer=True), "clause depth"),
        )),
        Record("paragraph", "a body paragraph", (
            Field("text", CellValue(), "paragraph text"),
        )),
        Record("bullets", "a bulleted list", (
            Field("items", ListOf(CellValue()), "bullet items"),
        )),
        Record("table", "a grid table", (
            Field("rows", ListOf(ListOf(CellValue()), non_empty=True), "rows; the first row sets the column count", required=True),
            Field("columnWidthsInches", ListOf(Number(minimum=0)), "ignored: columns share the page width evenly"),
        )),
    ),
)

CONTRACT_DOCUMENT = Record("contract", "the values office merge writes as a .docx contract when the form has no bundled template", (
    FORM_FIELD,
    Field("title", CellValue(), "centered bold title"),
    Field("fontName", CellValue(), f"body font, default {FONT_KOREAN_DOCX}"),
    Field("fontSize", Number(minimum=1), "body size in points"),
    Field("page", Record("page", "page setup", (Field("marginInches", Number(minimum=0), "every margin, default 0.9"),)), "page setup"),
    Field("blocks", ListOf(CONTRACT_BLOCK, non_empty=True), "the content", required=True),
))

ROW_AMOUNT_MISMATCH = IssueKind("ROW_AMOUNT_MISMATCH", ERROR, "a row's amount is not its quantity times its unit price", "correct the row's amount, or the quantity or unit price if one of those is wrong")
SUPPLY_TOTAL_MISMATCH = IssueKind("SUPPLY_TOTAL_MISMATCH", ERROR, "the supply total is not the sum of the row amounts", "correct the supply total, or the row that is wrong")
ROW_VAT_MISMATCH = IssueKind("ROW_VAT_MISMATCH", ERROR, "a row's VAT is not the VAT rate times the row's supply amount", "correct the row's VAT, or its amount if that is wrong")
VAT_MISMATCH = IssueKind("VAT_MISMATCH", ERROR, "the VAT total is not the sum of the row VATs, or without row VATs not the VAT rate times the supply total", "correct the VAT line")
GRAND_TOTAL_MISMATCH = IssueKind("GRAND_TOTAL_MISMATCH", ERROR, "the grand total is not the supply total plus the VAT", "correct the grand total line")
AMOUNT_IN_WORDS_MISMATCH = IssueKind("AMOUNT_IN_WORDS_MISMATCH", ERROR, "the amount in words, where the jurisdiction writes one, does not match the grand total", "rewrite the amount in words from the grand total")
AMOUNT_UNREADABLE = IssueKind("AMOUNT_UNREADABLE", ERROR, "a quantity, price or total holds no number", "write the value as a number, with or without thousands separators")
NO_AMOUNTS_FOUND = IssueKind("NO_AMOUNTS_FOUND", WARNING, "the input holds no quantity, unit price and amount columns and no contract amount, so nothing was checked", "check the values of a priced form, or of a contract with totalAmount")

AMOUNT_ISSUE_KINDS = (ROW_AMOUNT_MISMATCH, ROW_VAT_MISMATCH, SUPPLY_TOTAL_MISMATCH, VAT_MISMATCH, GRAND_TOTAL_MISMATCH, AMOUNT_IN_WORDS_MISMATCH, AMOUNT_UNREADABLE, NO_AMOUNTS_FOUND)

GUIDE_INPUTS = (
    ("merge", "form", "the values for a .pdf", PAPERWORK_DOCUMENT),
    ("merge", "form", "the values for a .docx without a bundled template", CONTRACT_DOCUMENT),
)
GUIDE_ISSUES = (
    ("merge", "form", (GLYPH_NOT_COVERED, RENDERER_UNAVAILABLE, RENDER_FAILED)),
    ("check", "form", AMOUNT_ISSUE_KINDS),
)


def form_lines() -> list[str]:
    lines = []
    for jurisdiction in JURISDICTIONS:
        with_template = [slug for slug in form_slugs(jurisdiction.code) if Form(jurisdiction, slug).template_path is not None]
        lines.append(f"  {jurisdiction.code}: {', '.join(form_slugs(jurisdiction.code))}")
        if with_template:
            lines.append(f"    a bundled .docx template fills these, from the fields below: {', '.join(with_template)}")
    return lines


def jurisdiction_lines() -> list[str]:
    return [line for jurisdiction in JURISDICTIONS for line in jurisdiction_summary(jurisdiction)]


def jurisdiction_summary(jurisdiction: Jurisdiction) -> list[str]:
    columns = jurisdiction.columns
    rate = f"{jurisdiction.tax_rate_percent}%" if jurisdiction.tax_rate_percent is not None else "taxRatePercent, when the values state it,"
    tax = f"{rate} of each row's amount when rows have a {columns.tax} column, else of the supply total; a row in items.untaxedRows carries none"
    if jurisdiction.tax_rate_percent is None:
        tax += "; without a stated rate the tax line is only added to the total"
    words = f"; meta \"{jurisdiction.amount_in_words.label}\" holds the amount in words: {jurisdiction.amount_in_words.example}" if jurisdiction.amount_in_words else ""
    return [
        f"  {jurisdiction.code} ({jurisdiction.name}): labels in {jurisdiction.language}; dates {jurisdiction.date_format}; currency {jurisdiction.money.currency or 'as the form names it'}",
        f"    item columns {columns.quantity}, {columns.unit_price}, {columns.amount}, {columns.tax}; tax {tax}; rounding: {jurisdiction.money.rounding_rule}{words}",
    ]


def template_guide_lines() -> list[str]:
    lines = []
    for name in template_names():
        lines.append(f"  {name}")
        lines.append(f"    required: {', '.join(caller_fields(name))}")
        lines.extend(list_lines(name) + default_lines(name) + optional_lines(name) + derived_lines(name))
    return lines


def list_lines(template_name: str) -> list[str]:
    fields = list_fields(template_name)
    return [f"    non-empty lists, one numbered paragraph per item: {', '.join(fields)}"] if fields else []


def optional_lines(template_name: str) -> list[str]:
    fields = optional_paragraph_fields(template_name)
    return [f"    paragraph left out when blank: {', '.join(fields)}"] if fields else []


def default_lines(template_name: str) -> list[str]:
    defaults = default_values(template_name)
    if not defaults:
        return []
    return ["    defaults: " + ", ".join(f"{field}={value!r}" for field, value in defaults.items())]


def derived_lines(template_name: str) -> list[str]:
    return [f"    derived when empty: {field}" for field in derived_values(template_name)]


def amount_rule_lines() -> list[str]:
    return [
        "  input: values naming their form, with items whose headers hold the jurisdiction's item columns, or a contract with totalAmount",
        "  row amount = quantity x unit price; supply total = sum of row amounts; grand total = supply total + tax",
        "  items.totals lists supply total, tax and grand total in that order",
        "  the command only reports facts in details and never rewrites the input",
    ]


GUIDE_SECTIONS = (
    ("form", "Forms (office merge <jurisdiction>/<form> <values.json> <output>; each one's spec is references/paperwork/<jurisdiction>/<form>.md)", form_lines),
    ("form", "Jurisdictions", jurisdiction_lines),
    ("form", "Fields of the bundled .docx templates", template_guide_lines),
    ("form", "Amount rules of office check <values.json>", amount_rule_lines),
)
