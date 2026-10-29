---
name: crm
description: Keep the company's customer and partner relationships — organizations it sells to, partners with or buys from, the people it talks to there, the deals in its pipeline, and the work recorded against them. Use for 고객사, 거래처, 파트너, 연락처, 담당자, 영업, 거래, 딜, 파이프라인, 리드, 미팅 기록, 통화 기록, 수주, 실주, CSV로 고객 가져오기, customer, account, contact, deal, pipeline, sales follow-up. Colleagues are person_list's; the company's own facts and funding rounds are company-data's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "crm_organization_list crm_organization_add crm_organization_update crm_organization_archive crm_contact_list crm_contact_add crm_contact_update crm_contact_archive crm_opportunity_list crm_opportunity_add crm_opportunity_update crm_opportunity_move crm_opportunity_archive crm_activity_list crm_activity_save crm_vocabulary_get crm_vocabulary_set crm_record_import company_record_list"
---

# CRM

Call the typed CRM operations directly. Their descriptors say what each one takes and does, and this skill covers only how they fit together. The CRM holds four things, each resting on the one before it: an organization, the contacts who work there, the deals with it, and the activity recorded against an organization or a deal.

## Order

- Read before you write. A record the matching `_list` already holds is changed, never added twice, and identical facts need no write.
- Build from the bottom: a missing organization first, then the contact, then the deal.
- Types, pipelines and stages are the company's words. Take them from `crm_vocabulary_get`.
- When a hint for a record or a colleague answers with candidates, the requester chooses, never you.
- A deal's worth, people and dates are `crm_opportunity_update`; its stage is only `crm_opportunity_move`. An investment deal's round comes from `company_record_list`.

## Activity

A call, meeting, email or note with a customer is `crm_activity_save` against its organization and, when there is one, its deal. Use it instead of `task_add` or `event_add`, because it writes the same task and ties it to the customer. Record only what the requester stated.

## Bulk import

Many organizations or contacts from a spreadsheet go through `crm_record_import`, never one `_add` per row. Run it with `dryRun` first, and report what it would create, update and skip, and each refused line with its reason. Import the organizations before the contacts that name them.

## Replies

Confirm each write in one line that names the record and what changed. List deals as a table of deal, organization, stage, amount and expected close date. Do not show IDs unless asked. Do not report a write that did not happen.
