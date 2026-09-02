---
name: calendar
description: Read or write the workspace calendar with calendar capability operations. Use this whenever the user asks to add, find, update, cancel, delete, or check meetings, schedules, 일정, 캘린더, 미팅, 회의, 약속, or reminders, even if they do not explicitly say "calendar."
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "event_add event_list event_update event_delete"
---

# Workspace Calendar

Call the typed calendar operations directly; their descriptors define fields and results. The Work calendar is exposed through CalDAV and ICS, so clients can subscribe or sync without making Google Calendar the default write path.

## Rules

- Prefer Work calendar operations over Google Workspace operations for ordinary schedule requests.
- Decide by the user's intent, not by the noun they used. Meetings, appointments, attendance blocks, visits, and time blocks are calendar events; deliverables, deadlines, todos, requests, handoffs, and completion targets are work.
- For a deadline-driven deliverable with a due time, call `task_add` and also `event_add` for the deadline or reminder.
- For completion of a task-like item, use `task_update`. Do not mark calendar events with `[완료]`.
- Do not ask approval before `event_add`, `event_list`, or `event_update`; ask before `event_delete`.
- Resolve relative dates from runtime temporal context. Ask one concise question when date, time, or duration is ambiguous.
- For all-day events, set `isWholeDay` and use the next-day boundary for the end. Put attendee hints in `participantPersonHints` using only names, @handles, or emails supplied by the user; the requester is included by default unless the entry is delegated or an announcement.
- Set `everyoneAttends` for an event the whole company is invited to, which leaves it with no attendee list. Choose reminder leads from 1, 2, 3, 6, 12, 24, or 48 hours according to preparation needs.
- `event_update` and `event_delete` take a single `eventHint`: the exact event ID or the exact current event title from a event_list result, resolved server-side to the canonical event. Use `event_list` first when neither is known precisely; if the hint does not uniquely resolve, the runtime fails with a candidates list — retry with the exact ID or title from it instead of guessing.
- Report created, updated, or listed events as an attendee line `참석자: <names>` (plain display names, no @handles; omit it when no attendee resolves) followed by a Markdown table with exactly these columns, one row per event: `일시 | 일정 | 장소 | 메모`. Translate the labels only when replying in another language; event IDs stay out of the table. External attendee invitations are not supported; mention that CalDAV clients can add them after sync.
