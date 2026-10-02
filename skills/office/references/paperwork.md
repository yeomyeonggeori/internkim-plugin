# Company Paperwork

A company form is named `<jurisdiction>/<form>`, such as `kr/quote` or `intl/invoice`, and filled with `<skill>/scripts/office merge <jurisdiction>/<form> <values.json> <output>`. Do not substitute `office create`, ad-hoc DOCX blocks, or hand-written scripts: letterhead, approval boxes, item tables, seals, and fixed wording belong here. SKILL.md's rules for source truth, totals, verification, and contracts apply.

## Catalog and specs

The jurisdiction is where the document has legal effect: `kr` for a Korean company's Korean forms, `intl` otherwise. Read the form's spec first at `references/paperwork/<jurisdiction>/<form>.md`; it is the source of truth for required content, fixed wording, output format, and the values JSON. A `kr` spec quotes in Korean what the form prints and explains it in English; write every `<placeholder>` value in Korean. `<skill>/scripts/office guide form` lists every form, what each jurisdiction prints and computes, and the fields of the bundled contract templates.

## Workflow

1. Identify the form and jurisdiction, then read the matching spec even when a similar document exists in conversation.
2. Call `company_info_get` for the language. If required `missingFields` or legal attributes are absent, ask once for all the missing values, save them through `company_info_set`, and copy optional logo or stamp images in a single terminal command.
3. Compare the spec's required fields with the request. Ask only for missing critical names, counterpart, dates, amounts, or terms; never invent them. Write "Not provided" in the document's language (미기재 in Korean) only for optional fields.
4. Register with `company_document_register` before filling, using the form name and a concise summary. Put the returned document number in the values JSON.
5. Write the spec-shaped values JSON; its `form` names the form. For quantities, prices, tax or a contract amount, run `<skill>/scripts/office check <values.json>` first and fix every issue it reports. Then run `office merge <jurisdiction>/<form> <values.json> <storageDirectory>/<filename>.pdf`, or `.docx` where the spec says so, and deliver the file. Do not reproduce the values schema in a reply.
6. Run `office check` on the output, then `office render` it and look at the pages, then call `company_document_update` with the delivered path. If the registered storage directory is not writable, use the requester documents area and record that path.

A `.pdf` output draws the form on letterhead. A `.docx` output fills the form's bundled contract template where it has one, and otherwise writes the contract from the blocks in the values.

## Rules

- `office check <values.json>` reports amount facts and never rewrites; `office guide form` states each jurisdiction's arithmetic and rounding. The figures you fix are the source's, not the check's.
- Include every clause and checklist item required by a spec's Standard clauses or Density gate. Do not abridge contracts.
- Past documents are found with `company_document_list` or `company_document_search`; answer from the stored summary before opening a file.
