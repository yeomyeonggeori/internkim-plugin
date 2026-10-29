---
name: crm
description: Keep the company's customer and partner relationships — organizations it sells to, partners with or buys from, the people it talks to there, the deals in its pipeline, and the work recorded against them. Use for 고객사, 거래처, 파트너, 연락처, 담당자, 영업, 거래, 딜, 파이프라인, 리드, 미팅 기록, 통화 기록, 수주, 실주, CSV로 고객 가져오기, customer, account, contact, deal, pipeline, sales follow-up. Colleagues are person_list's; the company's own facts and funding rounds are company-data's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "crm_organization_list crm_organization_add crm_organization_update crm_organization_archive crm_contact_list crm_contact_add crm_contact_update crm_contact_archive crm_opportunity_list crm_opportunity_add crm_opportunity_update crm_opportunity_move crm_opportunity_archive crm_activity_list crm_activity_save crm_vocabulary_get crm_vocabulary_set crm_record_import company_record_list person_list"
---

# CRM

Call the typed CRM operations directly; their descriptors define fields and results. The CRM holds four things, each resting on the one before it: an organization, the contacts who work there, the deals with it, and the activity recorded against an organization or a deal.

## Before writing

- Read before you write. Call the matching `_list` with a `query` before any `_add`. A record already held is changed with `_update`, never added twice. Identical facts need no write.
- Build from the bottom. A contact or a deal names an organization the CRM already holds, so add a missing organization first, then the contact, then the deal.
- Refer to a record with its hint: its exact ID, or its name or current title exactly as the list returned it. A deal's hint is never the new title you are about to give it.
- Types, pipelines and stages are the company's words. Read `crm_vocabulary_get` before you choose one, and never invent a type, pipeline or stage it does not list.
- A colleague who owns a relationship or takes part in work is named in `ownerPersonHint` or `participantPersonHints`. When the request names them by a fragment, call `person_list` and pass the exact name it returns. When several people answer to a name, the requester chooses.

## Deals

- `crm_opportunity_add` opens a deal at an open stage. `crm_opportunity_update` changes its worth, people and dates. Only `crm_opportunity_move` changes its stage.
- A move into a closing stage settles what the deal was worth and cannot be undone. Put it to the requester first, with the deal, the stage and the amount. A move into lost needs the reason the requester gave; do not supply one yourself.
- A deal that was already won or lost when it is first recorded is opened, then moved.
- Money goes in `amount` as stated, with its currency. Never convert or estimate it.
- An investment deal names its funding round with `fundingRoundHint`, from `company_record_list`.

## Activity

A call, meeting, email or note with a customer is recorded with `crm_activity_save` against its organization and, when there is one, its deal. An activity is a task, so it shows on the task board. Set `isEvent` only when it belongs on the calendar too. To change recorded work, read `crm_activity_list` and pass its `activityHint`. Put what was said or decided in `note`, in the requester's words, and record only what the requester stated.

## Bulk import

Many organizations or contacts from a spreadsheet go through `crm_record_import`, not one `_add` per row. Name the CSV by its workspace path in `attachments` and map each field to a header exactly as the file writes it in `columns`. Run `dryRun` first, and report how many records it would create, update and skip, and each refused line with its reason. Import contacts after the organizations they name. Choose `onDuplicate` from what the requester asked, and skip when they did not say.

## Putting away and vocabulary

Archive an organization, contact or deal only when the requester asks. Archiving keeps everything recorded against it. A deal that was lost is moved to lost instead. A person who left a customer is archived, or moved to their new organization with `crm_contact_update`.

`crm_vocabulary_set` is an administrator's. It replaces both lists at once, so send back every current type and pipeline with the change.

## Replies

Confirm each write in one line that names the record and what changed. List deals as a table of deal, organization, stage, amount and expected close date. List people by name and title. Do not show IDs unless the requester asks for one. When a call fails or a hint is ambiguous, say so and show the candidates it returned. Do not report a write that did not happen.
