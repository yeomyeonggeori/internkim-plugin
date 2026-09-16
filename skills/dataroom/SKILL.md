---
name: dataroom
description: Keep, file and search the company data room, the document archive behind every fact. Use for 데이터룸, 자료실, 문서 보관, 실사 자료, 증빙, 계약서 찾기, data room, due diligence, archive, evidence, "where is the document", filing a received contract or report, finding what a number rests on. Do not use to create documents (paperwork owns generation) or to record numbers (company-data owns metrics).
compatibility: Requires python3 and a terminal; in internkim, the company document ledger tools.
metadata:
  kim.intern.tool-references: "company_info_get company_document_register company_document_update company_document_list company_document_search company_document_upload company_document_download shell"
---


Command blocks below write `SKILL_DIR` where this skill's own directory belongs.

# Data Room

A data room is the company's document archive, filed by domain, where a domain is a folder and a clearance. In internkim the document row is the truth and the tree is its export; standalone, the tree is the truth. `references/domains.md` lists the fourteen domains, their clearances and where a document goes when subject and clearance disagree. `scripts/dataroom.py` keeps a tree in shape and bootstraps its own dependencies through `skill_runtime.py`; never run `pip install` directly.

## Finding

1. Start from `company.json` and `INDEX.md`; they are the map. Never list the tree.
2. Search with `company_document_search`, or in a tree with `python3 SKILL_DIR/scripts/dataroom.py search <dir> <query> [--path 03-finance/2026]`. Each hit is one line: path, id, date, title, summary. The summary carries the fact and its size; answer from it when it can.
3. Read the sidecar `<file>.md` before the original, and the original only when the sidecar cannot answer. `company_document_download` with `documentHint`, or `storagePath` plus `fileName` for a derived part, answers a signed URL. An original goes to the requester alone, never onward.

## Filing

1. Choose the domain by clearance, then by subject: a term sheet is governance, an NDA is a contract. A domain at clearance 2 or 3 takes a person's confirmation before filing.
2. Run `python3 SKILL_DIR/scripts/dataroom.py ingest <dir> <file> --domain <domain> --title <title> --kind <kind> --date <YYYY-MM-DD> --summary <fact>`. It copies the file to `<domain>/YYYY-MM-DD-slug.ext`, hashes it, derives text into the sidecar and the parts under `.derived/<sha256>/`, and regenerates the catalogs and index. Never copy a file into the tree by hand.
3. Write the summary yourself, under 200 characters, when the derived opening is not the fact. Set `--supersedes <id>` for a new version; the old document stays and is marked superseded. Nothing is overwritten or edited in place.
4. In internkim, `company_document_upload` with the domain's `clearance` and the file's `sha256` answers a `storagePath` of the form `<company>/dataroom/<clearance>/<sha256>` and a signed `uploadURL`: PUT the original, then each derived part with its `fileName`. Then `company_document_register` with the sidecar's title, summary, `domain`, `clearance`, `date`, `sha256` and `storagePath`, naming a replaced document with `supersedesHint`. A moved or renamed document is fixed with `company_document_update`.
5. A domain above the requester's clearance takes a submission: pass `--clearance <theirs>` and the document waits in `inbox/`, registered at their clearance with `domain` set, until an administrator raises it. Say so to the requester.
6. Publishing is an administrator's copy into `00-public` naming its source in `published`.

## Keeping

- `python3 SKILL_DIR/scripts/dataroom.py check <dir>` prints one line per departure from the standard and exits non-zero; fix every line. `index <dir>` regenerates `INDEX.md` and every catalog when check reports one stale.
- `init <dir> --slug <slug> --name ko=<name> --name en=<name>` creates an empty tree with `company.json`; in internkim that file mirrors the record and is never edited by hand.
- A number lives in the company metrics; the data room holds the document it came from, named by `id`.
