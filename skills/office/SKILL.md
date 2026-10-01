---
name: office
description: Create, read, edit, validate, and attach office files — Word .docx, PDF, Excel .xlsx/.csv/.tsv, slide decks (HTML, PDF, PPTX), and standardized Korean company forms and contracts on letterhead. Use for reports, memos, letters, workbooks, formulas, decks, pitch decks, PowerPoint, Keynote, 워드, 문서, 보고서, PDF, 엑셀, 스프레드시트, 표, 발표자료, 파워포인트, 피피티, 견적서, 거래명세서, 청구서, 발주서, 품의서, 지출결의서, 회의록, 주간업무보고, 출장보고서, 재직증명서, 경력증명서, 휴가신청서, 위임장, 오퍼레터, 근로계약서, 비밀유지계약서, NDA, 업무협약서, MOU, 용역계약서, quotation, invoice, purchase order, certificate, and contract requests.
compatibility: Requires python3 and uv, and bun or node 18 to draw pages; no browser or office suite. The first run installs the packages the scripts declare, and the first `--ocr` run installs an OCR engine of about 150 MB, so both need network access. Korean text needs a Korean-capable TTF or TTC font. Company forms and reading attached files need InternKim's tool server.
metadata:
  kim.intern.tool-references: "read company_info_get company_info_set company_document_register company_document_update company_document_list company_document_search"
---

# Office Files

One command, `<skill>/scripts/office <format> <verb> [arguments]`, writes and checks every office file. Pick the row for the work, read only that row's reference, and follow it. `<skill>/scripts/office --help` lists every command, and each command's own `--help` lists its arguments.

## Route the work

| Work | Commands | Reference |
| --- | --- | --- |
| Word document, report, memo, letter, template; a PDF whose words matter more than their placement | `doc export`, `doc create`, `doc edit`, `doc read`, `doc apply`, `doc merge`, `doc render`, `doc check`, `doc validate` | `references/doc.md` |
| Existing PDF to read, look at, extract, split, merge, or append to; a PDF whose placement is the point | `pdf read`, `pdf render`, `pdf create`, `pdf edit`, `pdf validate` | `references/pdf.md` |
| Workbook, CSV or TSV cleanup, formulas, charts | `sheet create`, `sheet edit`, `sheet read`, `sheet apply`, `sheet merge`, `sheet check`, `sheet render`, `sheet validate` | `references/sheet.md` |
| Deck, presentation, PPTX, or checking an existing .pptx | `deck check`, `deck build`, `deck read`, `deck apply`, `deck merge`, `deck restore`, `deck image` | `references/deck.md` |
| Converting a file to another format (md, docx, html, pdf, xlsx, xls, xlsb, ods, csv, pptx; the guide lists every route) | `convert` | `office guide convert` |
| Standardized company form or contract on letterhead (견적서, 품의서, 증명서, 계약서, NDA, MOU) | `paperwork check`, `paperwork render`, `paperwork fill` | `references/paperwork.md` |

A standardized form belongs to paperwork even when it ships as .docx or PDF: its letterhead, approval boxes, seals, and fixed clauses live there. Work the listed commands do not cover, such as merging PDFs, goes in a task-local Python file run with `<skill>/scripts/office python <script.py> [arguments]`, which provides every office package.

## Rules for every format

**Source truth.** Supplied files and pasted data are the source of truth. Preserve names, products, people, dates, amounts, IDs, and units exactly, and put the source title, organization, and period in visible content as well as the filename. A missing value is written as the user's-language equivalent of "Not provided"; never invent contacts, totals, vendors, prices, or background.

**Totals.** Compute totals from the source numbers in code and check that they equal any total the source states before writing the file.

**Earlier files.** For a file from an earlier task, use its workspace copy, not a delivered attachment, and read its exact path before answering about it or changing it. Keep the same filename for every later edit.

**File naming.** Documents, PDFs, and workbooks live at `~/documents/<title>.<ext>`, with any Markdown source beside them. Decks live in `artifacts/<deck-slug>/` and deliver from `artifacts/<deck-slug>/build/`. Company forms go to the storage directory their registration returns.

**Results.** Every command prints one JSON result: `status` is ok, warning, or error, and each issue carries a stable `code`, a `location`, a `suggestion` sentence, and `fix`: operations to pass as they are to that format's `apply` once any `<value>` is filled in. `<skill>/scripts/office guide <format>` indexes its commands and codes, `guide <format> <verb>` gives that command's fields and one line per operation, and `guide <format> <verb> <operation>` that operation's fields.

**Verify before attaching.** Run the final check the format's reference names and look at the pages it renders. Pass the source names, dates, totals, and key labels as `--required-text` where the command takes it. Read every warning, revise real problems, then attach only the accepted final output. Say what visual uncertainty remains.

**Korean fonts.** Korean text needs a Korean-capable font. The commands find one from a single list (Nanum Gothic, Noto Sans CJK, Apple SD Gothic Neo); never fall back to a built-in Latin font for Korean. Decks use the bundled Paperlogy font.

**Dependencies.** The `office` command installs its packages into its own environment on first use. Never run pip or uv yourself, and keep dependency caches apart from source documents.

**Tool server.** Only company forms (`company_info_*`, `company_document_*`) and reading an attached file (`read`) call InternKim's tool server. Every other command runs locally.

**Contracts.** A contract is a draft for review; say so when delivering it, without adding disclaimer text to the document.
