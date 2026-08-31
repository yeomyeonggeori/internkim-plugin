---
name: internkim-api
description: Read and change a company's internkim workspace over its public API — tasks and todos, calendar events, people, messages, hosted sites, documents. Use for 업무, 할 일, 일정, 캘린더, 사람, 메시지, 사이트, task, todo, schedule, or any request to look something up in internkim or record it there.
compatibility: Requires python3, network access to the internkim API, and a personal access token in INTERNKIM_TOKEN.
metadata:
  kim.intern.tool-references: "shell"
---


In every terminal command below, `<skill>` is this skill's own directory — the one holding this `SKILL.md`.

# internkim API

One script reaches every tool the caller's token may use. The catalog and the input schemas come from the API itself, so this file names no tool and copies no schema. Ask the API what it offers, then call it.

## Credentials

The script reads one thing: `INTERNKIM_TOKEN`. Where that comes from is the host's business, not this skill's.

A personal access token is issued from the signed-in account settings in the internkim web app. `scripts/store_token.sh` puts one in this computer's own secret store — macOS Keychain, or libsecret on Linux — and teaches the shell profile to read it back, so no file here holds the token. When the script reports no token, say so and let the user run that script; never ask them to paste a token into the conversation.

`INTERNKIM_API_URL` overrides the address for a self-hosted company. It defaults to `https://api.intern.kim/v1`.

## Workflow

1. List what this token may call:

```json
{
  "command": "python3 <skill>/scripts/internkim_api.py tools",
  "workingDirectoryPath": "<skill>"
}
```

2. Read the schema of the tool you picked. It carries every field name, enum, and requirement:

```json
{
  "command": "python3 <skill>/scripts/internkim_api.py schema task_add",
  "workingDirectoryPath": "<skill>"
}
```

3. Call it with a JSON object of that tool's own fields:

```json
{
  "command": "python3 <skill>/scripts/internkim_api.py call task_add --input '{\"title\":\"...\",\"status\":\"completed\"}'",
  "workingDirectoryPath": "<skill>"
}
```

`--input` also reads from stdin when omitted, which is the safer shape for anything holding quotes or newlines.

Skip step 2 only when a schema from step 1 or an earlier call in this same conversation already told you the fields. Never assume a field you have not seen in a schema.

## Rules

- **The catalog is the contract.** Tool names and fields change. Run `tools` before the first call of a conversation instead of relying on a name you remember; a name that worked last month may not exist now.
- **Hints are natural references, resolved server-side.** Tools that change an existing record take a hint field — the exact current title or the record's ID, never a new or intended title. When a hint does not resolve, the answer carries the candidates it did find; put those to the user and let them pick.
- **Names go through the people list.** When a request names somebody partly or by a given name alone, look the person up first and pass the exact name the workspace holds.
- **Resolve dates before calling.** Turn "내일", "next Tuesday", "this week" into the concrete format the schema asks for. The API resolves nothing.
- **One call per intent.** A tool that creates is not a tool that updates; read the descriptions rather than reusing a create call with an ID in it.

## Reading the answer

The script prints the API's own JSON. Read `outcome` first:

- `succeeded` — the work happened. `result` holds it, and `effects` names each record created, changed, or deleted.
- `failed` — the work did not happen. `message` says why, in words meant for a person; relay it rather than retrying the same input.

A transport or credential problem prints `{"status": "error", "message": ...}` and exits non-zero. That is this script speaking, not the API.

Do not tell the user something was recorded until an answer with `outcome: succeeded` says so.

## Destructive calls

Some tools delete. Their descriptions say so, and the API may require an approval the caller has to grant. Confirm with the user before calling one, and never call one to tidy up after your own mistake without saying what you are about to remove.
