---
name: calendar
description: Read or write the workspace calendar with calendar capability operations. Use this whenever the user asks to add, find, update, cancel, delete, or check meetings, schedules, 일정, 캘린더, 미팅, 회의, 약속, or reminders, even if they do not explicitly say "calendar."
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "event_add event_list event_update event_delete"
---

# Workspace Calendar

Call the typed calendar operations directly; their descriptors define fields and results. The Work calendar is exposed through CalDAV and ICS, so clients can subscribe to it or sync it.

## Rules

- Decide by the user's intent, not by the noun they used. Meetings, appointments, attendance blocks, visits, and time blocks are calendar events; deliverables, deadlines, todos, requests, handoffs, and completion targets are work.
- For a deadline-driven deliverable with a due time, call `task_add` and also `event_add` for the deadline or reminder.
- For completion of a task-like item, use `task_update`. Do not mark calendar events with `[완료]`.
- Resolve relative dates from runtime temporal context. Ask one concise question when date, time, or duration is ambiguous.
- Report created, updated, or listed events as an attendee line `참석자: <names>` (plain display names, no @handles; omit it when no attendee resolves) followed by a Markdown table with exactly these columns, one row per event: `일시 | 일정 | 장소 | 메모`. Translate the labels only when replying in another language; event IDs stay out of the table. External attendee invitations are not supported; mention that CalDAV clients can add them after sync.
