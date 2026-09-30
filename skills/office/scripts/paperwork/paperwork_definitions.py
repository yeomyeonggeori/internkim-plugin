from amounts import ROUNDING_RULE, VAT_RATE_PERCENT
from office_result import ERROR, WARNING, IssueKind
from office_schema import AnyOf, Boolean, CellValue, Field, ListOf, Number, Record, Text, Variant
from template_context import caller_fields, default_values, derived_values
from template_fields import template_list_fields, template_names


LABELED_VALUE = Record("labeled value", "one label and its value", (
    Field("label", CellValue(), "the label"),
    Field("value", CellValue(), "the value"),
))

PROFILE = Record("profile", "the company_info_get result, pasted whole; the letterhead reads these fields", (
    Field("name", CellValue(), "company name; name or companyName is required"),
    Field("companyName", CellValue(), "company name when name is absent"),
    Field("logoPath", CellValue(), "logo image at the letterhead's left"),
    Field("legalAttributes", ListOf(LABELED_VALUE), "the first two print on the letterhead, such as 사업자등록번호"),
    Field("registrationNumber", CellValue(), "printed as 사업자등록번호 when legalAttributes is empty"),
    Field("representative", CellValue(), "representative's name"),
    Field("representativeTitle", CellValue(), "title before the name, default 대표"),
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
    Field("totals", ListOf(LABELED_VALUE), "right-aligned total lines, the last one emphasized"),
))

RECIPIENT = Record("recipient", "the addressee block", (
    Field("label", CellValue(), "caption above the lines, default 수신"),
    Field("lines", ListOf(CellValue()), "addressee lines"),
))

PAPERWORK_SECTION = Record("section", "a titled block of paragraphs and bullets", (
    Field("title", CellValue(), "section title"),
    Field("paragraphs", ListOf(CellValue()), "paragraphs"),
    Field("bullets", ListOf(CellValue()), "bullet items"),
))

SIGNATURE = Record("signature", "the dated signature line", (
    Field("date", CellValue(), "date line"),
    Field("line", CellValue(), "signer line; (인) is appended"),
    Field("stamp", Boolean(), "place profile.stampPath on the signer line"),
))

PAPERWORK_DOCUMENT = Record("document", "the JSON of paperwork render to a .pdf; each spec under references/paperwork has its skeleton", (
    Field("title", Text(non_empty=True), "centered document title", required=True),
    Field("documentNumber", CellValue(), "printed as 문서번호 under the title"),
    Field("profile", PROFILE, "company profile for the letterhead", required=True),
    Field("approvalLine", ListOf(Text()), "approval box captions, left to right"),
    Field("recipient", RECIPIENT, "addressee"),
    Field("meta", ListOf(LABELED_VALUE), "label-value table under the title"),
    Field("items", ITEMS, "item table"),
    Field("sections", ListOf(PAPERWORK_SECTION), "body sections"),
    Field("notes", AnyOf((Text(), ListOf(CellValue()))), "centered closing lines"),
    Field("signature", AnyOf((Text(), SIGNATURE)), "signature; text becomes date on its first line and signer after"),
    Field("footer", CellValue(), "footer line on every page"),
    Field("fontPath", Text(), "TTF or TTC to embed; default the first Korean-capable font installed"),
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

CONTRACT_DOCUMENT = Record("contract", "the JSON of paperwork render to a .docx, for a clause the standard templates cannot express", (
    Field("title", CellValue(), "centered bold title"),
    Field("fontName", CellValue(), "body font, default 맑은 고딕"),
    Field("fontSize", Number(minimum=1), "body size in points"),
    Field("page", Record("page", "page setup", (Field("marginInches", Number(minimum=0), "every margin, default 0.9"),)), "page setup"),
    Field("blocks", ListOf(CONTRACT_BLOCK, non_empty=True), "the content", required=True),
))

QUANTITY_HEADERS = ("수량", "Qty")
UNIT_PRICE_HEADERS = ("단가", "Unit price")
AMOUNT_HEADERS = ("공급가액", "Amount")
TAX_HEADERS = ("세액", "Tax")
WORDS_LABELS = ("합계금액",)

ROW_AMOUNT_MISMATCH = IssueKind("ROW_AMOUNT_MISMATCH", ERROR, "a row's amount is not its quantity times its unit price", "correct the row's amount, or the quantity or unit price if one of those is wrong")
SUPPLY_TOTAL_MISMATCH = IssueKind("SUPPLY_TOTAL_MISMATCH", ERROR, "the supply total is not the sum of the row amounts", "correct the supply total, or the row that is wrong")
ROW_VAT_MISMATCH = IssueKind("ROW_VAT_MISMATCH", ERROR, "a row's VAT is not the VAT rate times the row's supply amount", "correct the row's VAT, or its amount if that is wrong")
VAT_MISMATCH = IssueKind("VAT_MISMATCH", ERROR, "the VAT total is not the sum of the row VATs, or without row VATs not the VAT rate times the supply total", "correct the VAT line")
GRAND_TOTAL_MISMATCH = IssueKind("GRAND_TOTAL_MISMATCH", ERROR, "the grand total is not the supply total plus the VAT", "correct the grand total line")
AMOUNT_IN_WORDS_MISMATCH = IssueKind("AMOUNT_IN_WORDS_MISMATCH", ERROR, "the Korean amount in words does not match the grand total", "rewrite the amount in words from the grand total")
AMOUNT_UNREADABLE = IssueKind("AMOUNT_UNREADABLE", ERROR, "a quantity, price or total holds no number", "write the value as a number, with or without thousands separators")
NO_AMOUNTS_FOUND = IssueKind("NO_AMOUNTS_FOUND", WARNING, "the input holds no quantity, unit price and amount columns and no contract amount, so nothing was checked", "pass the document JSON of a priced form or a contract context with totalAmount")

AMOUNT_ISSUE_KINDS = (ROW_AMOUNT_MISMATCH, ROW_VAT_MISMATCH, SUPPLY_TOTAL_MISMATCH, VAT_MISMATCH, GRAND_TOTAL_MISMATCH, AMOUNT_IN_WORDS_MISMATCH, AMOUNT_UNREADABLE, NO_AMOUNTS_FOUND)

GUIDE_INPUTS = (
    ("paperwork render <document.json> <output>.pdf", PAPERWORK_DOCUMENT),
    ("paperwork render <document.json> <output>.docx", CONTRACT_DOCUMENT),
)
GUIDE_ISSUES = (("paperwork check", AMOUNT_ISSUE_KINDS),)


def template_guide_lines() -> list[str]:
    lines = []
    for name in template_names():
        lines.append(f"  {name}")
        lines.append(f"    required: {', '.join(caller_fields(name))}")
        lines.extend(list_lines(name) + default_lines(name) + derived_lines(name))
    return lines


def list_lines(template_name: str) -> list[str]:
    fields = template_list_fields(template_name)
    return [f"    non-empty lists: {', '.join(fields)}"] if fields else []


def default_lines(template_name: str) -> list[str]:
    defaults = default_values(template_name)
    if not defaults:
        return []
    return ["    defaults: " + ", ".join(f"{field}={value!r}" for field, value in defaults.items())]


def derived_lines(template_name: str) -> list[str]:
    return [f"    derived when empty: {field}" for field in derived_values(template_name)]


def amount_rule_lines() -> list[str]:
    return [
        f"  input: the document JSON of paperwork render with items.headers holding {', '.join(QUANTITY_HEADERS + UNIT_PRICE_HEADERS + AMOUNT_HEADERS)}, or the context JSON of paperwork fill service-agreement",
        "  row amount = quantity x unit price; supply total = sum of row amounts; grand total = supply total + VAT",
        f"  row VAT = {VAT_RATE_PERCENT}% of the row amount when rows have a {' or '.join(TAX_HEADERS)} column; VAT total = sum of row VATs, else {VAT_RATE_PERCENT}% of the supply total",
        f"  rounding: {ROUNDING_RULE}",
        "  items.totals lists supply total, VAT and grand total in that order; meta \"합계금액\" holds the amount in words",
        "  amount in words: \"일금 일백만원정\" for 1,000,000; a trailing 整 counts as 정",
        "  the command only reports facts in details and never rewrites the input",
    ]


GUIDE_SECTIONS = (
    ("Templates of paperwork fill <template> <context.json> <output>.docx; the context JSON holds these fields", template_guide_lines),
    ("Amount rules of paperwork check <input.json>", amount_rule_lines),
)
