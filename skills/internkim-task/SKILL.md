---
name: internkim-task
description: Add, find, update, or complete weekly work items when the user asks to add, record, request, find, change, or complete work, todos, 업무, deadlines, or task notes.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "task_add task_list task_update task_delete person_list"
---

# 업무 관리

Use the typed work capability operations for work items; descriptors define fields and results, and the runtime supplies identity and approval. In Korean replies, do not call the product `Flow` unless the user explicitly uses that English name.

## Routing and workflow

- Decide by intent, not by the noun used. Deliverables, deadlines, todos, requests, handoffs, and completion targets are work. Meetings, appointments, attendance blocks, locations, and time blocks are calendar events.
- A deadline-driven deliverable uses `task_add` and, when a due time belongs on the calendar, `event_add` too. Completion uses `task_update`, not `event_update`.
- Add work directly only to the requester's own list. Work for another person is a `요청`; use `targetPersonHint` only when the person is explicit. Include the requester as a participant only when joint work is implied.
- Title the work, not the sentence that asked for it: a short noun phrase, with no participant names and no conversational wording. Who took part belongs in the person fields. Add goal, size, status, start date, or end date only when supported. Select size by the established XS–XXL scale: XS is a tiny change, S small, M day-sized, L multi-day, XL complex, and XXL a milestone that must be split.
- `task_update` and `task_delete` take a single `taskHint`: the exact task ID or the exact task title from a task_list result, resolved server-side to the canonical task. Use `task_list` first when neither is known precisely; if the hint does not uniquely resolve, the runtime fails with a candidates list — retry with the exact ID or title from it instead of guessing.
- Update with at least one mutable field; completion sets status to `completed`. `task_update` also changes people: `ownerPersonHint` reassigns the task, and `participantPersonHints` replaces the participant set, so send everyone who takes part and not only the person being added. Delete only on explicit request, passing the exact ID or title as `taskHint`. Approval authorizes deletion but does not identify the target.
- `category` and `type` accept only labels this workspace registers. Write the label you saw in a `task_list` result; an unregistered one fails with the registered labels, so retry against those rather than inventing a new label.
- Current-week listing is the default. Use week offsets for another period, including `weekFrom -1, weekTo -1` for last week, `weekFrom -3, weekTo 0` for the last four weeks, and a wide range such as `weekFrom -520` for history.
- A person hint resolves against the workspace roster: an exact ID, email, or @handle, otherwise a name that uniquely contains the hint. When a message names someone by a given name alone or by a fragment, call `person_list` and pass the exact name it returns. If a hint matches several people, the runtime returns the candidates and requires you to ask — the user chooses, never you. When a person hint fails to resolve, retry it against the returned candidates or ask; never drop the person and record the work without them, which answers a different request than the one that was made.

## Replies and failures

Report successful created, updated, or listed work as a Markdown table with exactly these columns, one row per task: `상태 | 업무 | 유형 | 크기 | 참여자`. `업무` is the task title. Status values in results are canonical English (planned, in_progress, completed, requested, paused, rejected, stopped); write them in the user's language in the table (Korean: 예정, 진행, 완료, 요청, 일시정지, 기각, 중단). `참여자` is the participant's `displayName`, falling back to the participant name. Write people as plain names everywhere; platform handles never appear in replies. To actually notify someone, write `@` plus their display name (the result's `mention` value) — the runtime resolves it to the platform's own mention. Translate the headers only when replying in another language. Task IDs, week codes, goals, content, and categories stay out of the table; give one in prose only when the user asks for it. If an owner is ambiguous, show the returned candidates by name; if an operation fails, explain it honestly and do not fabricate a task.
