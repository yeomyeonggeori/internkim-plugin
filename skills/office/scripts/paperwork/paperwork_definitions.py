from office_schema import AnyOf, Boolean, CellValue, Field, ListOf, Number, Record, Text, Variant


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

TEMPLATE_CONTEXTS = {
    "employment-contract": {
        "required": ["companyName", "companyPhone", "companyAddress", "representative", "employeeName",
                     "startDate", "workplace", "duties", "workStartTime", "workEndTime", "breakStart",
                     "breakEnd", "workDays", "weeklyHoliday", "monthlySalary", "bonus", "payday",
                     "paymentMethod", "contractDate"],
        "optional": ["endDate", "employeeAddress", "employeePhone", "otherAllowances", "insurances"],
        "lists": [],
        "defaults": {"otherAllowances": "없음", "insurances": "☑ 고용보험  ☑ 산재보험  ☑ 국민연금  ☑ 건강보험",
                     "employeeAddress": "", "employeePhone": "", "endDate": ""},
    },
    "service-agreement": {
        "required": ["clientName", "clientAddress", "clientRepresentative", "providerName", "providerAddress",
                     "providerRepresentative", "serviceName", "startDate", "endDate", "totalAmount",
                     "totalAmountKorean", "vatNote", "bankAccount", "penaltyRate", "warrantyMonths",
                     "jurisdiction", "contractDate"],
        "optional": [],
        "lists": ["scopeItems", "payments", "deliverables"],
        "defaults": {"penaltyRate": "1.25", "warrantyMonths": "3"},
    },
    "nda": {
        "required": ["partyAName", "partyAAddress", "partyARepresentative", "partyBName", "partyBAddress",
                     "partyBRepresentative", "purpose", "termYears", "survivalYears", "jurisdiction", "contractDate"],
        "optional": ["penaltyAmount"],
        "lists": [],
        "defaults": {"termYears": "5", "survivalYears": "3", "penaltyAmount": ""},
    },
    "mou": {
        "required": ["orgAName", "orgARepresentative", "orgBName", "orgBRepresentative", "purpose",
                     "termYears", "contractDate"],
        "optional": [],
        "lists": ["cooperationItems", "orgARoles", "orgBRoles"],
        "defaults": {"termYears": "2"},
    },
    "offer-letter": {
        "required": ["companyName", "representative", "candidateName", "position", "department", "workplace",
                     "startDate", "salary", "expiryDate", "offerDate"],
        "optional": ["equity", "probationNote"],
        "lists": ["benefits"],
        "defaults": {"equity": "", "probationNote": ""},
    },
}

GUIDE_INPUTS = (
    ("paperwork render <document.json> <output>.pdf", PAPERWORK_DOCUMENT),
    ("paperwork render <document.json> <output>.docx", CONTRACT_DOCUMENT),
)
GUIDE_ISSUES = ()


def template_guide_lines() -> list[str]:
    lines = []
    for name, manifest in TEMPLATE_CONTEXTS.items():
        lines.append(f"  {name}")
        lines.append(f"    required: {', '.join(manifest['required'])}")
        if manifest["optional"]:
            lines.append(f"    optional: {', '.join(manifest['optional'])}")
        if manifest["lists"]:
            lines.append(f"    non-empty lists: {', '.join(manifest['lists'])}")
        if manifest["defaults"]:
            lines.append("    defaults: " + ", ".join(f"{field}={value!r}" for field, value in manifest["defaults"].items()))
    return lines


GUIDE_SECTIONS = (("Templates of paperwork fill <template> <context.json> <output>.docx; the context JSON holds these fields", template_guide_lines),)
