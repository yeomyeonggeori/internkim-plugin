---
name: people
description: Find colleagues and keep the company directory and organization chart — who works here, job titles, teams, who reports to whom, start and last days, administrator rights — and bring people in or out of the company. Use for 직원, 동료, 누구야, 조직도, 팀, 부서, 직책, 상급자, 입사, 퇴사, 초대, 계정 만들기, 비밀번호 초기화, 관리자 권한, 서클 채널, colleague, directory, org chart, team, onboarding, offboarding, invite, reset password. People at customers and partners are the crm skill's; who reads which data room category is the dataroom skill's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "person_list person_update person_invite person_withdraw person_password_reset person_message_delete team_list team_add team_update team_delete circle_list circle_channel_add circle_channel_delete"
---

# People

Call the typed operations directly; their descriptors define fields and results. The directory holds everybody who works here and the organization chart they sit on. Apart from someone correcting their own phone number and start date, changing it is an administrator's, and the record refuses anybody else. A refusal is the answer, not an error to work around.

## Finding people

`person_list` answers who someone is and who works here. Every other call takes a colleague as the requester wrote them, even a given name alone, and the server resolves it. When it answers with candidates, the requester chooses, never you.

## Directory and chart

- `person_update` changes only the fields it names. Ask the requester first before raising or lowering administrator rights, or marking somebody departed.
- A team is an organization on the chart. Read `team_list` before naming one. `team_add` puts nobody in it; move people with `person_update` and `teamHint`. A team with teams under it cannot be removed until those are moved or removed.
- An account that is not a person, such as a test account, is set to kind `other`, so it leaves the headcount and the chart.

## Bringing someone in

1. `person_invite` with their name, email and, when known, job title and team.
2. `person_update` for what the invite does not take, such as supervisor and start date.
3. The answer holds a temporary password that is readable only once. Give it to the requester alone and never post it in a shared conversation. `person_password_reset` answers the same way.

## Someone leaving

1. Set their last day with `person_update` `departureDate`, which may be ahead. They stay counted until it passes.
2. Only when the requester asks for their messages to go, call `person_message_delete`, before step 3, while they are still in the directory.
3. `person_withdraw` ends their sign-in and membership. Their attendance, leave and tasks still read. Set `purge` only when the requester asked to delete the account outright, such as an address added by mistake.

Each of these is irreversible. Name the person and what will happen, and let the runtime take the approval.

## Circle channels

A circle can have one private messenger channel whose members are exactly the circle's. Read `circle_list` for the circle's ID and current `channelName`. Adding and deleting one is an administrator's, and deleting takes that exact name.

## Replies

Confirm each write in one line with the person or team and what changed. Write people by name, never by handle or ID unless asked. Report a refused or ambiguous call with what it returned.
