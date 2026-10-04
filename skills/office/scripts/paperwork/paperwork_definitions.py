from __future__ import annotations

from core.office_result import ERROR, WARNING, IssueKind
from core.office_schema import AnyOf, Boolean, CellValue, Field, ListOf, Number, Record, Text, Variant
from paperwork.paperwork_design import FONT_KOREAN_DOCX
from fonts.font_files import FONT_PATH_MEANING
from paperwork.contract_plan import CONTRACT_ISSUE_KINDS
from paperwork.contract_template import TERM_TYPES, ContractTemplate
from paperwork.forms import Form, form_slugs
from paperwork.jurisdictions import JURISDICTIONS, Jurisdiction
from doc.doc_definitions import GLYPH_NOT_COVERED
from render.renderer import RENDER_FAILED, RENDERER_UNAVAILABLE


REGISTERED_DOCUMENT_NUMBER = "<the number company_document_register returned>"

LABELED_VALUE = Record("labeled value", "one label and its value", (
    Field("label", CellValue(), "the label"),
    Field("value", CellValue(), "the value"),
))

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

APPROVER = Record("approver", "one approval box: the role on top and, when the request names one, the approver under it", (
    Field("role", Text(non_empty=True), "the box caption, such as the approver's title", required=True),
    Field("name", CellValue(), "the approver's name the request gives"),
))

SIGNATURE = Record("signature", "the dated signature line", (
    Field("date", CellValue(), "date line"),
    Field("line", CellValue(), "signer line; the jurisdiction's seal mark, where it has one, is appended"),
    Field("stamp", Boolean(), "place the company's kept seal on the signer line"),
))

FORM_FIELD = Field("form", Text(non_empty=True), "the form these values fill, <jurisdiction>/<form> such as kr/quote; office merge takes it from its first argument and office check from here")

PAPERWORK_DOCUMENT = Record("document", "the values office merge draws on letterhead as a .pdf; each spec under references/paperwork has its skeleton; a value written null is drawn as a blank to fill by hand and listed in details.blanks", (
    FORM_FIELD,
    Field("title", Text(non_empty=True), "centered document title", required=True),
    Field("documentNumber", CellValue(), "the number company_document_register returned for this document, as it is; printed under the title after the jurisdiction's document-number label"),
    Field("approvalLine", ListOf(AnyOf((Text(), APPROVER))), "approval boxes left to right, each a role or {role, name}; the approvers the request names, in its order"),
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
    ("merge", "form", (GLYPH_NOT_COVERED, RENDERER_UNAVAILABLE, RENDER_FAILED, *CONTRACT_ISSUE_KINDS)),
    ("check", "form", (*AMOUNT_ISSUE_KINDS, *CONTRACT_ISSUE_KINDS)),
)


def form_lines() -> list[str]:
    lines = []
    for jurisdiction in JURISDICTIONS:
        with_template = [slug for slug in form_slugs(jurisdiction.code) if Form(jurisdiction, slug).contract_template is not None]
        lines.append(f"  {jurisdiction.code}: {', '.join(form_slugs(jurisdiction.code))}")
        if with_template:
            lines.append(f"    a bundled contract template prints these as .docx, from the terms below: {', '.join(with_template)}")
    return lines


def jurisdiction_lines() -> list[str]:
    return [line for jurisdiction in JURISDICTIONS for line in jurisdiction_summary(jurisdiction)]


def jurisdiction_summary(jurisdiction: Jurisdiction) -> list[str]:
    columns = jurisdiction.columns
    rate = f"{jurisdiction.tax_rate_percent}%" if jurisdiction.tax_rate_percent is not None else "taxRatePercent, when the values state it,"
    tax = f"{rate} of each row's amount when rows have a {columns.tax} column, else of the supply total; a row in items.untaxedRows carries none"
    if jurisdiction.tax_rate_percent is None:
        tax += "; without a stated rate the tax line is only added to the total"
    words = amount_in_words_summary(jurisdiction.amount_in_words) if jurisdiction.amount_in_words else ""
    return [
        f"  {jurisdiction.code} ({jurisdiction.name}): labels in {jurisdiction.language}; dates {jurisdiction.date_format}; currency {jurisdiction.money.currency or 'as the form names it'}",
        f"    item columns {columns.quantity}, {columns.unit_price}, {columns.amount}, {columns.tax}; tax {tax}; rounding: {jurisdiction.money.rounding_rule}{words}",
    ]


def amount_in_words_summary(words) -> str:
    return f"; merge writes an empty meta \"{words.label}\" value from the grand total, such as \"{words.line(1_000_000)}\" for 1,000,000, and checks one written by hand ({words.example})"


def template_guide_lines() -> list[str]:
    lines = [
        "  a template prints every clause it lists; each {{ term }} a printed clause states is a typed value the values give, and no template supplies one",
        "  clauses: {<clause key>: {heading?, paragraphs}} replaces that clause's text, keeping its place and number",
        "  addedClauses: [{key, heading, paragraphs, after?}] adds a clause after the clause named by after, else last; its key names its subject and is no template clause's key",
        "  removedClauses: [<clause key>] leaves a clause out only when the request removes it; numbers close up",
        "  a term written null prints a blank line to fill by hand where the clause states it, and merge lists it in details.blanks",
        "  clause paragraphs may write {{ <term> }} to state a term and {{ article:<clause key> }} for that clause's number",
        "  term types: " + "; ".join(f"{name}: {meaning}" for name, meaning in TERM_TYPES.items()),
    ]
    for jurisdiction in JURISDICTIONS:
        for slug in form_slugs(jurisdiction.code):
            template = Form(jurisdiction, slug).contract_template
            if template is not None:
                lines.extend(template_lines(f"{jurisdiction.code}/{slug}", template))
    return lines


def template_lines(name: str, template: ContractTemplate) -> list[str]:
    return [
        f"  {name}",
        "    clauses: " + ", ".join(template.article_keys),
        *(f"    {term.describe()}" for term in template.terms),
    ]


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
    ("form", "Terms and clauses of the bundled contract templates", template_guide_lines),
    ("form", "Amount rules of office check <values.json>", amount_rule_lines),
)
