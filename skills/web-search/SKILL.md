---
name: web-search
description: Search the public web or fetch a specific URL when the user's request needs external or current information that is not already available in the conversation, an attachment, or another skill. Use for news, prices, schedules, documentation, or any fact you cannot already answer from provided context.
compatibility: Requires InternKim's tool server.
metadata:
  kim.intern.tool-references: "web_search web_fetch"
---

# Web Search

Check the conversation and attachments first. When external or current information is needed, call `web_search` for discovery or `web_fetch` for specific URLs; descriptors define exact fields and result shapes.

## Search

Use search for public-web queries, then read the synthesized answer before selecting returned results for citations or follow-up fetches. Use location, language, domain allowlists, exclusions, and a small result limit only when the request needs them.

## Fetch

Fetch only URLs returned by search or supplied by the user. Keep content limits appropriate to the question, and report fetch errors rather than fabricating content, titles, URLs, or snippets.

## Rules

- Both operations need network access. If the provider reports `local_only`, `missing_openrouter_key`, or another error, say the web tool is unavailable rather than guessing.
- Prefer primary sources for factual claims, preserve returned URLs exactly, and cite only observed sources.
