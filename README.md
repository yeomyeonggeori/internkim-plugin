# internkim-plugin

Skills from the [InternKim](https://intern.kim) agent, packaged as an
[Agent Plugins](https://agent-plugins.org) 1.1.0 plugin so they run on any
conforming client.

| Skill | What it does |
| --- | --- |
| `pdf` | Builds and validates PDFs, including Korean typography |
| `spreadsheet` | Creates and edits `.xlsx` workbooks |
| `presentation` | Builds HTML decks and exports PPTX |
| `calculator` | Evaluates arithmetic exactly |
| `weather` | Reads Open-Meteo forecasts with a local cache |

## Requirements

Python 3 and [uv](https://docs.astral.sh/uv/) on `PATH`. Each skill declares its
own dependencies in `scripts/requirements.txt` and installs them into an
environment it creates on first use, so nothing has to be prepared in advance.

A host that already has a prepared interpreter can point the skills at it with
`BLUECLAW_BUILTIN_SKILLS_PYTHON`, and at a shared package cache with
`BLUECLAW_DEPENDENCY_CACHE`. Neither is required.

## Paths

Every terminal command in a `SKILL.md` writes `<skill>` where the skill's own
directory belongs — the directory holding that `SKILL.md`. Nothing here names a
host layout.

## Validation

```bash
skills-ref validate skills/<name>
```

All five skills pass the [Agent Skills](https://agentskills.io/specification)
reference validator.

## License

[Apache-2.0](LICENSE).
