# Company Paperwork

A company form is named `<jurisdiction>/<form>`, such as `kr/quote` or `intl/invoice`, and filled with `<skill>/scripts/office merge <jurisdiction>/<form> <values.json> <output>`. Do not substitute `office create`, ad-hoc DOCX blocks, or hand-written scripts: letterhead, approval boxes, item tables, seals, and fixed wording belong here. SKILL.md's rules for source truth, totals, verification, and contracts apply.

## Catalog and specs

The jurisdiction is where the document has legal effect: `kr` for a Korean company's Korean forms, `intl` otherwise. Read the form's spec first at `references/paperwork/<jurisdiction>/<form>.md`; it is the source of truth for required content, fixed wording, output format, and the values JSON. A `kr` spec quotes in Korean what the form prints and explains it in English; write every `<placeholder>` value in Korean. `<skill>/scripts/office guide form` lists every form, what each jurisdiction prints and computes, and the fields of the bundled contract templates.

## Workflow

1. Identify the form and jurisdiction, then read the matching spec even when a similar document exists in conversation.
2. Call `company_info_get` for the language. If required `missingFields` or legal attributes are absent, ask once for all the missing values, save them through `company_info_set`, and copy optional logo or stamp images in a single terminal command.
3. Compare the spec's required fields with the request. Ask only for missing critical names, counterpart, dates, amounts, or terms; never invent them. Write "Not provided" in the document's language (미기재 in Korean) only for optional fields.
4. Register with `company_document_register` before filling, using the form name and a concise summary. Put the returned document number in the values JSON.
5. Write the spec-shaped values JSON; its `form` names the form. Run `<skill>/scripts/office check <values.json>` first and fix every issue it reports: it checks amounts, and a contract's terms and clauses. Then run `office merge <jurisdiction>/<form> <values.json> <storageDirectory>/<filename>.pdf`, or `.docx` where the spec says so, and deliver the file. Do not reproduce the values schema in a reply.
6. Run `office check` on the output, then `office render` it and look at the pages, then call `company_document_update` with the delivered path. If the registered storage directory is not writable, use the requester documents area and record that path.

A `.pdf` output draws the form on letterhead. A `.docx` output prints the form's bundled contract template where it has one, and otherwise writes the contract from the blocks in the values.

## Terms and clauses

What the request states wins over every default. A spec's customary value or default fills only what the request leaves unsaid, and is written into the values; a template never supplies a term.

Every variable term of a bundled contract template is a typed value, and merge refuses a term a printed clause states but the values leave out. When the request words a matter a template clause already covers differently, such as a deadline, a ceiling, an exception or a licence, replace that clause through `clauses.<key>`, write `{{ <term> }}` where it states a typed term, and also replace any other clause whose standard wording would contradict it. Add a clause through `addedClauses` only for a matter no template clause covers. Never edit the merged file to change what a clause says. Merge's `details.clauses` and `details.terms` are what the contract says; report terms from them.

## Rules

- `office check <values.json>` reports amount facts and never rewrites; `office guide form` states each jurisdiction's arithmetic and rounding. The figures you fix are the source's, not the check's.
- Each row's tax follows that row's own tax status: list a row that carries no tax (exempt or zero-rated) in `items.untaxedRows` and write 0 in its tax cell.
- Include every clause and checklist item required by a spec's Standard clauses or Density gate. Do not abridge contracts.
- A drafter, author or signer the form names is the person the request names, else the requester; never the agent itself.
- Past documents are found with `company_document_list` or `company_document_search`; answer from the stored summary before opening a file.
