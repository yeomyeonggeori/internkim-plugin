---
name: office
description: Create, read, edit, validate, and attach office files — Word .docx, PDF, Excel .xlsx/.csv/.tsv, slide decks (HTML, PDF, PPTX), and standardized company forms and contracts on letterhead. Use for reports, memos, letters, workbooks, formulas, decks, pitch decks, PowerPoint, Keynote, 워드, 문서, 보고서, PDF, 엑셀, 스프레드시트, 표, 발표자료, 파워포인트, 피피티, 견적서, 거래명세서, 청구서, 발주서, 품의서, 지출결의서, 회의록, 주간업무보고, 출장보고서, 재직증명서, 경력증명서, 휴가신청서, 위임장, 오퍼레터, 근로계약서, 비밀유지계약서, NDA, 업무협약서, MOU, 용역계약서, quotation, invoice, purchase order, certificate, and contract requests. Use it whenever a task makes or changes one of these files, even a one-line PDF, instead of writing the file with a script: it sets the layout and fonts and checks the file before it is sent.
compatibility: Requires python3, uv, and bun or node 18; no browser or office suite. `scripts/office setup` prepares the Python packages, the renderer and the OCR engine once, and InternKim's host install runs it; no other command installs anything. Company forms and reading attached files need InternKim's tool server.
metadata:
  kim.intern.tool-references: "read company_info_get company_info_set company_image_upload company_document_register company_document_update company_document_list company_document_search"
---

# Office Files

One command, `<skill>/scripts/office <verb> <file> [options]`, makes and checks every office file. The verbs mean the same for every format, and the file's format picks what each does: `create` makes a new file from a source, `read` lists what a file holds, `apply` edits it with a batch of operations, `merge` fills a template or a bundled form, `check` finds what is wrong before delivery, `render` draws pages to look at, `convert` turns a file into another format. `<skill>/scripts/office --help` lists what each verb takes, and `office <verb> --help` its options.

## Route the work

| Work | Command | Reference |
| --- | --- | --- |
| Report, weekly report, status update, memo, postmortem, letter or notice, as .docx or .pdf | `merge report` or `merge letter` with the given values | `references/schemas.md` |
| Quotation, invoice or meeting minutes, as a file: PDF unless another format is named | `merge kr/quote`, `merge intl/invoice`, `merge kr/meeting-minutes` with the given values | `references/schemas.md` |
| Other long-form document, as .docx or .pdf | `create <title>.docx <title>.md` | `references/doc.md` |
| Change an existing .docx, .xlsx, .pptx or .pdf | `read`, then `apply` | the format's reference |
| Read, look at or take apart an existing PDF | `read`, `render` | `references/pdf.md` |
| New workbook, from the request or an attached CSV or TSV: data, summaries, comparisons, charts | `create <title>.xlsx <title>.workbook.json` | `references/schemas.md` |
| Change a workbook the person already has | `read`, then `apply` | `references/sheet.md` |
| Deck, presentation, PPTX | `DESIGN.md`, `outline.json` and `pages/NN.html`, each checked, then `create build/<deck>.pptx .` | `references/deck.md` |
| Fill a user's .docx, .xlsx or .pptx template | `merge` | `references/doc.md` |
| Every other document the form catalog has: transaction statement, purchase order, approval request, expense approval, business trip report, leave request, employment certificate, career certificate, power of attorney, offer letter, employment contract, NDA, MOU, service agreement | `merge <jurisdiction>/<form>` | `references/paperwork.md` |
| Another format of a file | `convert` | `office guide convert` |
| Verify before attaching | `check`, `render` | the format's reference |

A document the catalog has belongs to `merge <jurisdiction>/<form>` in either language and whatever format or wording the request uses: its letterhead, approval boxes, seal, and fixed clauses live there, and `create` is only for documents the catalog lacks. Work no verb covers, such as merging PDFs, goes in a task-local Python file run with `<skill>/scripts/office python <script.py> [arguments]`. That script never writes a new document, form, or workbook: those come only from `merge` or `create` in the table above, which compute every total, formula, and format from the values you give.

## Rules for every format

**Source truth.** Supplied files and pasted data are the source of truth. Preserve names, products, people, dates, amounts, IDs, and units exactly. A value the document needs that no source states is left blank, never invented: in a schema it is `null`. Deliver the document anyway; the reply names each blank field from the result's `details.blanks` and offers to complete the same file when the person sends the values.

**Totals.** Compute totals from the source numbers in code and check that they equal any total the source states before writing the file.

**Earlier files.** For a file from an earlier task, use its workspace copy, not a delivered attachment, and read its exact path before answering about it or changing it. Keep the same filename for every later edit.

**File naming.** Documents, PDFs, and workbooks live at `~/documents/<title>.<ext>`, with any Markdown source beside them. Decks live in `artifacts/<deck-slug>/` and deliver from `artifacts/<deck-slug>/build/`. Company forms go to the storage directory their registration returns.

**Results.** Every command prints one JSON result: `status` is ok, warning, or error, and each issue carries a stable `code`, a `location`, a `suggestion` sentence, and `fix`: operations to pass as they are to `apply` on the same file once any `<value>` is filled in. `<skill>/scripts/office guide <kind>` indexes a kind of file's commands and codes, `guide <verb> <kind>` one command's fields, and `guide <verb> <kind> <operation>` one operation's.

**Verify before attaching.** Run `check` on the final file and look at the pages `render` draws, except a deck whose build result names `visualReview`, as `references/deck.md` says. Pass each source name, date, total, and key label as its own `--required-text`; a value is matched whole, commas included. A file made by `merge <schema>` or from a workbook declaration needs neither: code drew its layout from your values, so read its result's `blanks` and `views` and deliver it, without `check` or `render`. Read every warning, revise real problems, then attach only the accepted final output. Say what visual uncertainty remains.

**Fonts.** The skill ships its fonts and draws every page with them, so a page looks the same on any host; `<skill>/scripts/office guide` lists each family and its kind. A font a file names that the skill does not ship is drawn with the shipped family of its kind. A .docx or .pptx carries the shipped fonts it uses, so the recipient needs nothing installed; a workbook cannot carry fonts and keeps Office's own. Pass a font path only when the user supplies a font file.

**Dependencies.** `<skill>/scripts/office setup` prepares everything the commands read, and no other command installs anything. A command that reports `DEPENDENCIES_UNAVAILABLE` or `RENDERER_UNAVAILABLE` names the setup to run; when that setup cannot write into the skill directory, tell the user the skill was not prepared. Never run pip or uv yourself, and keep dependency caches apart from source documents.

**Tool server.** Only company forms (`company_info_*`, `company_image_upload`, `company_document_*`) and reading an attached file (`read`) call InternKim's tool server. Every other command runs locally.

**Contracts.** A contract is a draft for review; say so when delivering it, without adding disclaimer text to the document.
