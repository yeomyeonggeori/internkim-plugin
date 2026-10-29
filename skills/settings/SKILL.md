---
name: settings
description: Read and change how the company and the agent are set up — the company's name in the app, time zone, language, currency, work locations and annual leave; what the requester is notified about; the agent's name, handle and introduction; and how the agent works with the requester, what to call them, tone, reply language and the morning briefing. Use for 설정, 시간대, 통화, 근무지, 알림 끄기, 알림 설정, 봇 이름, 에이전트 이름, 호칭, 말투, 답변 언어, 아침 브리핑, settings, time zone, notifications, agent name, persona, morning briefing. The company's legal profile is company-data's.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "company_settings_get company_settings_update notification_settings_get notification_settings_set persona_identity_get persona_identity_update persona_profile_get persona_profile_update"
---

# Settings

Call the typed operations directly. Their descriptors say what each one takes and does, and this skill covers only how they fit together. The company settings and the agent's identity are company-wide and an administrator's. Notifications and the persona profile belong to the requester alone.

## Routing

- The company's name in the app, time zone, language, currency, work locations and annual leave are `company_settings_get` and `company_settings_update`. The legal name a document prints is the company-data skill's. The rest of the leave policy is the attendance skill's.
- Whole categories of notice are `notification_settings_set`. One conversation is the messages skill's `conversation_mute`. A reminder the requester set up is stopped through the scheduled-task skill.
- The agent's names, handle and introduction for everyone are `persona_identity_update`. How the agent treats the requester, such as what to call them, tone, reply language and the morning briefing, is `persona_profile_update`.
- A list field replaces the whole list. Read the setting first and send the whole list back with the change.

## Replies

Confirm each change in one line with the setting and its new value. Never report a change that did not happen.
