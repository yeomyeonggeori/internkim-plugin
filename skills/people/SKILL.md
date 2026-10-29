---
name: people
description: Find colleagues and keep the company directory and organization chart — who works here, job titles, teams, who reports to whom, start and last days, administrator rights — and bring people in or out of the company. Use for 직원, 동료, 누구야, 조직도, 팀, 부서, 직책, 상급자, 입사, 퇴사, 초대, 계정 만들기, 비밀번호 초기화, 관리자 권한, 서클 채널, colleague, directory, org chart, team, onboarding, offboarding, invite, reset password. People at customers and partners are the crm skill's; who reads which data room category is the dataroom skill's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "person_list person_update person_invite person_withdraw person_password_reset person_message_delete team_list team_add team_update team_delete circle_list circle_channel_add circle_channel_delete"
---

# People

Call the typed operations directly. Their descriptors say what each one takes and does, and this skill covers only how they fit together. The directory holds everybody who works here and the organization chart they sit on. Changing it is mostly an administrator's, and a refusal is the answer, not an error to work around.

## Routing

- Who someone is, or who works here, is `person_list`. Every other call takes a colleague as the requester wrote them. When it answers with candidates, the requester chooses, never you.
- Moving someone to a team is `person_update`, after `team_list`. Creating a team puts nobody in it.
- A test account or anything else that is not a person is set to kind `other` with `person_update`. It leaves the headcount and the chart, and the account stays.

## Bringing someone in

`person_invite`, then `person_update` for what the invite does not take, such as supervisor and start date. A temporary password from an invite or `person_password_reset` goes to the requester alone, never into a shared conversation.

## Someone leaving

1. `person_update` with their `departureDate`.
2. `person_message_delete`, only when the requester asked for their messages to go. It must come before step 3.
3. `person_withdraw`, with `purge` only when the requester asked for the account to be deleted outright.

## Replies

Confirm each write in one line with the person or team and what changed. Write people by name, never by handle or ID unless asked.
