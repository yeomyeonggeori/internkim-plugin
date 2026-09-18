---
name: scheduled-task
description: Create, update, or cancel scheduled, recurring, and finite repeated reminders, messages, reports, and follow-up tasks when the user asks to schedule, remind, repeat, change, cancel, or stop them.
compatibility: Requires a host that can schedule agent work.
metadata:
  kim.intern.tool-references: "schedule_create schedule_update schedule_cancel"
---

# Scheduled Task

A schedule is one piece of work the host carries out at a stated time or cadence: its instruction holds only what to do when it runs, and every when, how often, and until when lives in the schedule's own fields. To change a schedule that exists, name it as it is now and update it rather than cancelling and recreating it; to stop it, cancel it. After a write, say what will run, when, and when it stops, and never say a delivery has already happened.
