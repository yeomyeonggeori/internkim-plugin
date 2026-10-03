---
name: dataroom
description: File, find and share the company's document archive. Use for 데이터룸, 자료실, 문서 보관, 실사 자료, 증빙, 계약서 찾기, data room, due diligence, archive, evidence and filing received documents. Office creates documents; company-data records metrics.
compatibility: Requires python3 and a terminal. In InternKim, use the internkim MCP server declared by this plugin.
metadata:
  kim.intern.tool-references: "dataroom_get dataroom_category_update circle_list circle_update circle_member_update dataroom_links_get dataroom_link_add dataroom_link_delete dataroom_share_add dataroom_share_delete company_document_classify company_document_register company_document_update company_document_list company_document_search company_document_upload company_document_download bash"
---

# Data room

The archive belongs to the company. InternKim's central record owns its
categories, circles, document metadata and stored files. Blueclaw accesses
it as the requester. A standalone export is a local tree with `company.json`
and `INDEX.md`; its folders do not enforce access control.

Read `dataroom_get` for live categories and `circle_list` for who reads them. Codes
are stable mnemonic letters: a parent has one, an intermediate category has
two. Documents go in categories without children, including a parent with no
children, or `X`, the unclassified inbox. Parents with children are not filing
destinations.
Classification follows the document's primary business function. File format
and intended audience do not determine where it belongs.

## File

1. Extract enough text to identify the document. Call `company_document_classify`
   with its title and text or factual summary. It makes one decision-model
   request against the requester's available company categories. Keep `X` when
   context is insufficient. Never invent missing facts.
2. For an export, run `python3 SKILL_DIR/scripts/dataroom.py ingest <dir> <file>
   --category <code> --title <title> --summary <fact> --date <YYYY-MM-DD>`.
   The helper files the original as `<parent>/<category>/<name>.<id>.<extension>`,
   the same path the record uses, hashes it, writes its `<file>.md` sidecar,
   derives `<name>.<id>.content.txt` beside it and regenerates catalogs. Inspect
   its skipped derivations. Its packages come from
   `python3 SKILL_DIR/scripts/skill_runtime.py setup`, which InternKim's host
   install runs; the helper names that command when they are missing.
3. Register with `company_document_register`, keeping that category, title,
   factual summary, date and hash. Use `supersedesHint` for a replacement.
   Keep earlier versions.
4. Call `company_document_upload` with the registered `documentHint` and the
   original's `originalFileName`, then PUT the original to the returned signed
   URL. Upload `content.txt` and other derived parts with `fileName`. The
   original sits at `<company>/dataroom/<parent>/<category>/<name>.<documentID>.<extension>`
   and each derived part beside it as `<name>.<documentID>.<fileName>`.
5. An administrator can reclassify existing documents with
   `company_document_update`; their files move with them. Read the
   destination's circles first: moving a document changes who can read it.

## Find

Use `company_document_list` with `categoryCode` to browse a parent or
intermediate category, or `company_document_search` for a natural question.
Answer from summaries where possible. Download `content.txt` before the
original when it can answer. Access is enforced by the record and file store.

For an export, start with `company.json` and `INDEX.md`, then run
`python3 SKILL_DIR/scripts/dataroom.py search <dir> <query> [--path <category-path>]`.
Run `check <dir>` after filing and `index <dir>` to rebuild stale catalogs.
`init <dir> --slug <slug> --name en=<name>` creates an empty template.
A tree from an earlier schema is filed again into a new one; do not convert
permissions by matching old folder names.

## Share

A company member reads through the circles they belong to. A circle names the
categories it reads in `readableCategories`; a parent covers its current and
future children. Read circles and their members with `circle_list`.
Administrators place a member in circles with `circle_member_update`, which
replaces that member's circles at once, and create or edit a circle with
`circle_update`. Read the affected members before editing a circle, because
access changes immediately. A circle grants no editing or administrative
rights.

For a code-protected link, read `dataroom_links_get` for the circles the
requester can share. Use `dataroom_link_add` with the chosen circle, label,
lifetime and download permission. The default lifetime is three days and the
maximum is seven days. Return `/share/links/<linkID>` on the company's web
origin and the six digit code displayed once. The recipient enters the code and
accepts the confidentiality notice without an account. `dataroom_link_delete`
revokes an exact linkID.

To share with someone outside the company, lend them what one circle reads with
`dataroom_share_add`: an external email, or an explicitly public audience. An
external email accepts the invitation using that verified email and remains a
guest, outside company membership and circles. Return
`/share/invitations/<shareID>` for an email invitation, or `/share/<companyID>`
for a published room, using the company's web origin. Public publication
requires an explicit request and never includes `X`. Original downloads are
separately enabled with `canDownload`. Revoke by exact `shareID`; issued signed
URLs expire within ten minutes.
