# Company Paperwork

Create standardized business documents with the bundled letterhead renderer and the matching spec. Do not substitute `pdf create`, ad-hoc DOCX blocks, or hand-written scripts: letterhead, approval boxes, item tables, seals, and fixed wording belong here. SKILL.md's rules for source truth, totals, verification, and contracts apply.

## Catalog and specs

Read the requested language's spec first at `references/paperwork/<ko|en>/<slug>.md`; the spec is the source of truth for required content, fixed wording, output format, and the content JSON. `<skill>/scripts/office guide paperwork` lists every slug and whether it renders or fills a template.

## Workflow

1. Identify type and language, then read the matching spec even when a similar document exists in conversation.
2. Call `company_info_get` for the language. If required `missingFields` or legal attributes are absent, ask once for all the missing values, save them through `company_info_set`, and copy optional logo or stamp images in a single terminal command.
3. Compare the spec's required fields with the request. Ask only for missing critical names, counterpart, dates, amounts, or terms; never invent them. Use the user's-language equivalent of "미기재" only for optional fields.
4. Register with `company_document_register` before rendering, using the catalog slug and a concise summary. Put the returned document number in the content JSON.
5. Write the spec-shaped content JSON. For a form with quantities, prices, VAT or a contract amount, run `<skill>/scripts/office paperwork check <content.json>` first and fix every issue it reports. Then run `<skill>/scripts/office paperwork render <content.json> <storageDirectory>/<filename>.pdf` or the `paperwork fill` command the spec names, then deliver the generated PDF or DOCX to the requester. The spec and `<skill>/scripts/office guide paperwork` define the payload fields; do not reproduce their schema in a reply.
6. Validate the output, then run `<skill>/scripts/office pdf render <file.pdf>` and look at the pages, especially table-heavy forms and dense contracts, then call `company_document_update` with the actual delivered path. If the registered storage directory is not writable, use the requester documents area and record that path.

## Renderer choices

PDF specs use `paperwork render`; DOCX contracts use the bundled standard-form template through `paperwork fill`. A custom contract clause that the template cannot express is the only reason to use the fallback blocks renderer.

## Rules

- `paperwork check` reports amount facts and never rewrites; `office guide paperwork` states its arithmetic and rounding. The figures you fix are the source's, not the check's.
- Include every clause and checklist item required by a spec's Standard clauses or Density gate. Do not abridge contracts.
- Past documents are found with `company_document_list` or `company_document_search`; answer from the stored summary before opening a file.
