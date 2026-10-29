---
name: attendance
description: Clock in and out, correct attendance, and request, decide and count leave, with the company's working hours, leave types and holidays they are judged against. Use for 출근, 퇴근, 근태, 지각, 근무시간, 출퇴근 기록 수정, 휴가, 연차, 반차, 병가, 휴가 신청, 휴가 승인, 남은 연차, 복귀, 공휴일, 회사 휴무일, 근무제, clock in, attendance, time off, leave balance, holiday. Meetings and other time blocks are the calendar's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "attendance_add attendance_list attendance_update attendance_delete attendance_work_policy_get attendance_work_policy_set attendance_leave_policy_get attendance_leave_policy_set leave_request leave_list leave_balance leave_update leave_delete leave_decide leave_grant_set leave_return_early company_holiday_list company_holiday_add company_holiday_update company_holiday_delete company_settings_get"
---

# Attendance and leave

Call the typed operations directly. Their descriptors say what each one takes and does, and this skill covers only how they fit together. Attendance is when people arrive and leave. Leave is the time they are away. Both are judged against the work policy, the leave policy and the company's holidays.

## Routing

- Arriving or leaving is `attendance_add`. Someone on leave who says they are back is `leave_return_early`, which also clocks them in.
- A location comes from `company_settings_get`.
- To correct or remove a clock record, find it in `attendance_list` first.
- Meetings and other time blocks are the calendar's, not attendance.
- Questions about hours, working days, leave types and holidays are answered from `attendance_work_policy_get`, `attendance_leave_policy_get` and `company_holiday_list`, never from memory.

## Leave

- Take the kind from `registeredKinds` in `leave_list`.
- `days` counts working days only. Read `workingWeekdays` from `attendance_work_policy_get` and the span's `company_holiday_list`. When the span or the portion of a day is unclear, ask.
- A filed request waits for an administrator's `leave_decide`. Never say it is approved before then.
- To change, withdraw or decide a leave, find it in `leave_list` first.
- "Give them three more days" is `leave_balance`, then `leave_grant_set` with the total.
- When a person hint answers with candidates, the requester chooses, never you.

## Replies

Confirm each write in one line with the person, the day and the time or span, in the company time zone. Show leave as a table of person, kind, dates, days and status, with status in the requester's language: in Korean, 신청, 승인 and 반려. Never report a write that did not happen.
