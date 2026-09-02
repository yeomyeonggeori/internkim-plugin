---
name: scheduled-task
description: Create, update, or cancel scheduled, recurring, and finite repeated reminders, messages, reports, and follow-up tasks when the user asks to schedule, remind, repeat, change, cancel, or stop them.
compatibility: Requires a host that can schedule agent work.
metadata:
  kim.intern.tool-references: "schedule_create schedule_update schedule_cancel"
---

# Scheduled Task

Call the typed `schedule_create`, `schedule_update`, or `schedule_cancel` operation directly; descriptors define exact fields and results. Use `schedule_update` with the exact scheduleID from `schedule_list` to change an existing schedule instead of cancel-and-recreate. A schedule is bounded work, not an unsupported background loop.

## Create

- Put only the action to perform at run time in `taskInstruction`; cadence and stop conditions belong in structured schedule fields.
- Choose `kind: once` with `runAt` for one future run, `kind: interval` with `intervalSecond` for simple repeats, and `kind: cron` with `cronExpression` for calendar-like repeats.
- Set `timeZone` from context, using `Asia/Seoul` for Korean local-time requests when no better timezone is known. Set `maxRunCount` for a finite count and `expiresAt` for an end time.
- For a future direct message, make `taskInstruction` name the recipient, message, and DM delivery.
- Call `schedule_create`, then report what will run and when it will stop. Never claim that recurring delivery has already happened.

## Cancel

Use `schedule_cancel`'s scope for the user's schedules, current conversation, or explicitly observed schedule IDs. After success, report the number of schedules or waits cancelled; an approval request does not identify a target.
