---
name: settings
description: Read and change how the company and the agent are set up — the company's name in the app, time zone, language, currency, work locations and annual leave; what the requester is notified about; the agent's name, handle and introduction; and how the agent works with the requester, what to call them, tone, reply language and the morning briefing. Use for 설정, 시간대, 통화, 근무지, 알림 끄기, 알림 설정, 봇 이름, 에이전트 이름, 호칭, 말투, 답변 언어, 아침 브리핑, settings, time zone, notifications, agent name, persona, morning briefing. The company's legal profile is company-data's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "company_settings_get company_settings_update notification_settings_get notification_settings_set persona_identity_get persona_identity_update persona_profile_get persona_profile_update"
---

# Settings

Call the typed operations directly; their descriptors define fields and results. Four settings live here. Two are company-wide and an administrator's: the company settings and the agent's identity. Two belong to the requester alone: their notifications and their persona profile.

Every update changes only the fields it names, but a list replaces the whole list: `workLocations`, `names`, `preferences`. Read the current setting first and send the whole list back with the change.

## Company settings

- `company_settings_get` answers the time zone, language, currency, work locations and annual leave.
- `company_settings_update` changes what every colleague sees. Put it to the requester first, with the current value and the new one.
- `name` is the name the app shows. The legal name a document prints is `company_info_set`'s, in the company-data skill.
- `leaveDays` is the annual leave grant. The rest of the leave policy is the attendance skill's.

## Notifications

- `notification_settings_get` shows which categories the requester is told about and which conversations they muted. `notification_settings_set` turns categories on or off for them alone.
- A category answered with `isChoosable` false cannot be changed. Say so instead of calling.
- Muting one conversation is the messages skill's `conversation_mute`. Stopping a reminder the requester set up is the scheduled-task skill's.

## The agent's identity

`persona_identity_get` is who the agent is to the whole company: its names, handle, role and introduction. The first name is the one it introduces itself with. Changing it is an administrator's, and every colleague meets the agent by it, so put the change to the requester first.

## The requester's profile

`persona_profile_get` and `persona_profile_update` hold how the agent works with the requester: what to call them, what to know about them, preferences, tone, reply language and the morning briefing. Only the requester's own profile is reachable. Record what they asked for in their words. Turning the briefing off keeps its time.

## Replies

Confirm each change in one line with the setting and its new value. Never report a change that did not happen.
