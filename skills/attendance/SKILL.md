---
name: attendance
description: Clock in and out, correct attendance, and request, decide and count leave, with the company's working hours, leave types and holidays they are judged against. Use for 출근, 퇴근, 근태, 지각, 근무시간, 출퇴근 기록 수정, 휴가, 연차, 반차, 병가, 휴가 신청, 휴가 승인, 남은 연차, 복귀, 공휴일, 회사 휴무일, 근무제, clock in, attendance, time off, leave balance, holiday. Meetings and other time blocks are the calendar's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "attendance_add attendance_list attendance_update attendance_delete attendance_work_policy_get attendance_work_policy_set attendance_leave_policy_get attendance_leave_policy_set leave_request leave_list leave_balance leave_update leave_delete leave_decide leave_grant_set leave_return_early company_holiday_list company_holiday_add company_holiday_update company_holiday_delete company_settings_get person_list"
---

# Attendance and leave

Call the typed operations directly; their descriptors define fields and results. Attendance is when people arrive and leave. Leave is the time they are away. Both are measured against the work policy, the leave policy and the company's holidays. The record decides who may do what: a person writes their own recent records, and an administrator writes anybody's and any day's.

## Clocking in and out

- Someone who says they arrived or are leaving now is clocked with `attendance_add`, with no date or time. A stated past moment goes in `date` and `time`, in the company time zone.
- Someone on leave who says they are back is `leave_return_early`, which ends the leave and clocks them in. Do not clock them in separately.
- A location must be one `company_settings_get` lists. Omit it when they did not say where.
- A reason is the requester's own words, kept when given. Never ask for one, and never write one yourself.

## Correcting attendance

- Find the record first with `attendance_list`, then correct it with `attendance_update` or remove it with `attendance_delete`, naming the row exactly as the list showed it.
- Correct a day's clock-in and clock-out in one call.
- An answer with status `asked` means the request was beyond the requester's reach and the administrators have been told. That is the finished answer. Say an administrator was asked, and do not call again.

## Leave

- Take the kind from `registeredKinds` in `leave_list`, or from `attendance_leave_policy_get`. Whether it is paid follows from the kind, so never ask.
- `days` is the entitlement the leave spends, not the span it covers. Count only working days: read `workingWeekdays` from `attendance_work_policy_get` and the span's `company_holiday_list`. A half day is 0.5. When the span or the portion is unclear, ask.
- A request is filed as requested and grants nothing until an administrator decides it with `leave_decide`. Say it is waiting on a decision, never that it is approved.
- To fix a filed leave, read it with `leave_list` and pass its `leaveHint` to `leave_update`. To withdraw a request still waiting, or erase a leave that should never have been filed, use `leave_delete`. To refuse one, decide it rejected.
- "How many days do I have left" is `leave_balance`. When tracking is unlimited, say there is no fixed entitlement, not zero.
- `leave_grant_set` writes a total, not an increase. For "three more days", read `leave_balance` first and write the sum.
- Another person is named in `personHints` or `personHint`. Pass it as the requester wrote it, even a given name alone; the server resolves it, so do not look it up in `person_list` first. When it answers with candidates, the requester chooses, never you.

## Policies and holidays

- Answer questions about hours, working days, leave types and holidays from `attendance_work_policy_get`, `attendance_leave_policy_get` and `company_holiday_list`. Do not answer them from memory.
- The two `_policy_set` calls are an administrator's, and each one replaces the whole policy. Read the current one, change only what was asked, and send it all back. A new work policy applies from today, and earlier days keep theirs.
- Read `company_holiday_list` before adding a holiday. Removing one makes it a working day for everyone, so put it to the requester first.

## Replies

Confirm each write in one line with the person, the day and the time or span. Write times as 24-hour HH:MM in the company time zone. Show leave as a table of person, kind, dates, days and status. Write status in the requester's language: in Korean, 신청, 승인 and 반려. Never report a write that did not happen.
