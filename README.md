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
| `internkim-api` | Reads and changes a company's internkim workspace over its public API |

## Requirements

Python 3 and [uv](https://docs.astral.sh/uv/) on `PATH`. Each skill declares its
own dependencies in `scripts/requirements.txt` and installs them into an
environment it creates on first use, so nothing has to be prepared in advance.

A host that already has a prepared interpreter can point the skills at it with
`BLUECLAW_BUILTIN_SKILLS_PYTHON`, and at a shared package cache with
`BLUECLAW_DEPENDENCY_CACHE`. Neither is required.

`internkim-api` also needs a personal API key in `INTERNKIM_TOKEN`, issued from
the account settings of the internkim web app. It names no tool of its own: it
reads the catalog and the input schemas from the API at run time, so a tool
added or renamed there needs no change here.

## Paths

Every terminal command in a `SKILL.md` writes `<skill>` where the skill's own
directory belongs — the directory holding that `SKILL.md`. Nothing here names a
host layout.

## Validation

```bash
skills-ref validate skills/<name>
```

All six skills pass the [Agent Skills](https://agentskills.io/specification)
reference validator.

## License

[Apache-2.0](LICENSE).
