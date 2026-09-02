---
name: company-data
description: Record and look up company master data — metrics time series (연매출, 영업이익, MAU, 직원 수), history and assets (연혁, 투자 유치, 제품 출시, 특허, 인증, 수상, 레퍼런스), and the company document ledger. Use for 매출 기록, 지표 기록, 연혁 추가, 투자 이력, 회사 정보 수정, 우리가 보낸 계약서/견적서 조회, revenue record, funding history, company timeline requests. Do not use for creating documents — the paperwork skill owns document generation.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "company_info_get company_info_set company_metric_list company_metric_record company_record_list company_record_add company_record_update company_record_delete company_document_list company_document_search company_document_register"
---

# Company Data

Use the typed operations for the persistent profile, numeric time series, history and asset records, and document ledger. Their descriptors define exact fields and results. Record user-stated facts promptly and answer from stored tables rather than guessing.

## Metrics

For a new metric, first call `company_metric_list` for the relevant period. Identical data needs no write; a correction updates the existing period; only a genuinely new fact calls `company_metric_record`. Use one metric key across periods, choose year, quarter, or month deliberately, and never combine quarter and month. Money keeps the stated local `currency` and stated `valueUSD`; never estimate exchange rates. Non-money metrics use `unit` instead.

## Records

For history, funding, products, certifications, IP, awards, references, or grants, first call `company_record_list` for the category and period. Identical facts need no write; changed details use `company_record_update` with the observed ID; new facts use `company_record_add`. Delete only on explicit request. Use structured attributes when a category has repeatable details.

## Profile

Use `company_info_get` before answering or changing profile data. Call `company_info_set` with the requested language and only changed fields. Store country-specific identifiers in `legalAttributes`; never put company facts in files or memory instead of this table.

## Document ledger

Search with `company_document_search` before reading a file when a ledger summary can answer the question; use `company_document_list` for inventories. Save an attached received contract under the member documents area, then register it with kind and a concise summary. Do not use this skill to create documents.

## Rules

- Record only user-stated facts; never estimate values, dates, investors, or exchange rates.
- Confirm a successful write in one line with the metric or record, period, and value so mistakes surface immediately.
- These tables feed decks, business plans, and grant applications; preserve structured facts instead of replacing them with prose.
