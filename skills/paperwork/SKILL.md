---
name: paperwork
description: Create standardized company business documents on letterhead. Use for 견적서, 거래명세서, 청구서, 발주서, 품의서, 지출결의서, 회의록, 주간업무보고, 출장보고서, 오퍼레터, 근로계약서, 재직증명서, 경력증명서, 휴가신청서, 비밀유지계약서, NDA, 업무협약서, MOU, 용역계약서, 위임장, 서식, 공문, ERP 서류, quotation, invoice, purchase order, offer letter, employment contract, certificate requests. Do not use for free-form reports, memos, essays, or slide decks — use the docx or presentation skill for those.
compatibility: Requires python3, a terminal, and InternKim's tool server.
metadata:
  kim.intern.tool-references: "company_info_get company_info_set company_document_register company_document_update company_document_list company_document_search"
---


In every terminal command under `references/`, `<skill>` is this skill's own directory — the one holding this `SKILL.md`.

# Company Paperwork

Create standardized business documents with the bundled letterhead renderer and the matching spec. Do not substitute the pdf skill's `create_pdf.py`, ad-hoc DOCX blocks, or hand-written scripts: letterhead, approval boxes, item tables, seals, and fixed wording belong to this skill.

## Catalog and references

Read the requested language's spec first at `references/<ko|en>/<slug>.md`; the spec is the source of truth for required content, fixed wording, output format, and the content JSON. Supported slugs are `quote`, `transaction-statement`, `invoice`, `purchase-order`, `approval-request`, `expense-approval`, `meeting-minutes`, `weekly-report`, `business-trip-report`, `employment-certificate`, `career-certificate`, `leave-request`, `power-of-attorney`, `offer-letter`, `employment-contract`, `nda`, `mou`, and `service-agreement`.

## Workflow

1. Identify type and language, then read the matching spec even when a similar document exists in conversation.
2. Call `company_info_get` for the language. If required `missingFields` or legal attributes are absent, ask once for all the missing values, save them through `company_info_set`, and copy optional logo or stamp images in a single terminal command.
3. Compare the spec's required fields with the request. Ask only for missing critical names, counterpart, dates, amounts, or terms; never invent them. Treat requester-provided facts as the source of truth and use the user's-language equivalent of “미기재” only for optional fields.
4. Register with `company_document_register` before rendering, using the catalog slug and a concise summary. Put the returned document number in the content JSON.
5. Write the spec-shaped content JSON, run the bundled renderer or template filler, then deliver the generated PDF or DOCX to the requester. The typed descriptors and spec define payload fields; do not reproduce their schema in this guide.
6. Validate output and layout, especially table-heavy PDFs and contract density, then call `company_document_update` with the actual delivered path. If the registered storage directory is not writable, use the requester documents area and record that path.

## Renderer choices

PDF specs use `render_paperwork.py`; DOCX contracts use the bundled standard-form template and `fill_template.py`. A custom contract clause that the template cannot express is the only reason to use the fallback blocks renderer. Scripts bootstrap dependencies through `skill_runtime.py`; never run `pip install` directly. For Korean output, use an available Korean-capable font and keep shared dependency caches separate from source documents.

## Rules

- Verify line amounts, VAT, and totals before rendering; a computed total must equal the source values.
- Include every clause and checklist item required by a spec's Standard clauses or Density gate. Do not abridge contracts.
- Past documents are found with `company_document_list` or `company_document_search`; answer from the stored summary before opening a file.
- Contracts are drafts for review; say so when delivering them without adding disclaimer text to the document.
