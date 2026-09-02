---
name: skill-management
description: Create, add, update, or remove user-managed Blueclaw skills. Use for requests about making a new skill, writing SKILL.md, adding a skill, deleting a skill, removing a skill, or managing skills.
compatibility: Requires a host that can install and remove its own skills.
metadata:
  kim.intern.tool-references: "skill_add skill_remove"
---

# Skill Management

Call `skill_add` to create or update user-managed skills. Call `skill_remove` to remove user-managed skills.

Before writing a skill, capture the intent:

- What the skill should enable.
- When it should trigger, including realistic user phrases.
- The expected behavior or output.
- Which runtime capabilities it needs.
- Two or three realistic test prompts the user can try after creation.

Write `SKILL.md` content directly in the `content` argument to `skill_add`. Use only `name`, `description`, `license`, `compatibility`, `metadata`, and `tool-references` frontmatter fields. Put trigger scope in `description`; do not invent custom fields, summaries, tags, trigger hints, capability dependency fields, allowed profiles, generated indexes, or full-body embeddings.

Keep `SKILL.md` concise. Put essential workflow in the body. Put long domain knowledge in `references/`, deterministic repeated logic in `scripts/`, and output resources in `assets/`. When adding bundled resources, pass them through the `resources` argument to `skill_add` and mention each referenced resource from `SKILL.md`.

Scripts should be self-contained within the skill folder. Python helpers should run through a skill-local runtime wrapper that selects a preinstalled dependency environment first, then uses `uv` with `scripts/requirements.txt` into requester-owned temporary storage only when needed. Reuse `/workspace/shared/cache/dependencies` only as a package cache. Asset-local Node dependencies should follow the same pattern with `package.json`. Do not expose runtime paths outside `/workspace` as commands for the model to run. Do not write new skills that ask the model to stop and report missing import libraries as the primary recovery path.

Do not put evals, benchmark metadata, test prompts, or generated summaries in frontmatter. Mention suggested test prompts to the user after the skill is created.

Do not use shell commands or shell redirection to create, edit, or delete skill files directly. The skill capability derives the destination path from the skill name and enforces the runtime boundary.

User-managed skills live under `/workspace/.agents/skills/<name>`. Built-in skills are immutable and cannot be overwritten or removed.

After adding or removing a skill, tell the user that the change is available to future turns after skill retrieval refreshes. If `skill_add` returns warnings, report them as improvement suggestions, not as failure.
