# internkim-plugin

Skills from the [InternKim](https://intern.kim) agent, packaged as an
[Agent Plugins](https://agent-plugins.org) 1.0.0 plugin so they run on any
conforming client.

Three run on their own with a shell and Python.

| Skill | What it does |
| --- | --- |
| `calculator` | Evaluates arithmetic exactly |
| `weather` | Reads Open-Meteo forecasts with a local cache |
| `dataroom` | Files, checks and searches a company data room, locally or in the record |

Ten call InternKim's tool server, the `internkim` server that `mcp.json`
declares. Each names the tools it calls in its own `tool-references`.

| Skill | What it does |
| --- | --- |
| `internkim-task` | Adds, finds, updates and completes work items |
| `calendar` | Adds, lists, changes and removes calendar events |
| `scheduled-task` | Schedules work to run later or repeatedly |
| `direct-message` | Sends and schedules direct messages |
| `messages` | Reads, posts, edits and removes conversation messages |
| `mail` | Connects a mailbox, then reads, searches and sends mail |
| `office` | Creates, edits and validates `.docx`, PDF, `.xlsx` and decks, and fills company forms on letterhead; only the forms and reading attachments need the server |
| `website` | Scaffolds, builds, previews and publishes a site |
| `company-data` | Reads and records company profile, metrics and records |
| `web-search` | Searches the public web and fetches pages |

## Requirements

Python 3 and [uv](https://docs.astral.sh/uv/) on `PATH`. A skill that bundles
scripts declares its own dependencies in `scripts/requirements.txt` and installs
them into an environment it creates on first use, so nothing has to be prepared
in advance. `website` also needs [Bun](https://bun.sh), and `office` needs Bun
and a browser that speaks the Chrome DevTools Protocol to render decks.

`office` runs every command through one entry, `scripts/office <format>
<verb>`, which prepares that environment first; `scripts/office --help` lists
the commands. Each command prints one JSON result with a status and coded
issues, and `scripts/office guide <format>` prints the fields every input takes
and every code a command reports, generated from the validators themselves.

Those environments, the package cache and any host-supplied fonts live under
`XDG_CACHE_HOME`, falling back to `~/.cache` when it is unset. A host with a
shared package cache points `UV_CACHE_DIR` at it. Neither is required, and the
skills read no variable named after the host that runs them.

## Tool server

`mcp.json` declares `https://api.intern.kim/v1/mcp`, a Streamable HTTP server
that answers with the tools the signed-in member may use in their company. The
plugin carries no credential. The server follows MCP authorization: a request
without a token is answered `401` with a `WWW-Authenticate` header pointing at
its protected resource metadata, and a client that implements it signs the
member in through the browser and keeps the token itself.

A client that does not implement MCP authorization can send a personal access
token, issued from the account settings of the internkim web app, as
`Authorization: Bearer ik_…`. Configure that in the client; this repository
never holds one.

## Loading it

This repository holds nothing but the portable plugin: `plugin.json`,
`skills/` and `mcp.json`. How a client reads that layout is the client's own
affair, so no client-specific manifest or adapter code lives here.

| Client | How it loads the plugin |
| --- | --- |
| Codex | Reads the root `plugin.json`, `skills/` and `mcp.json` natively (openai/codex#36544). |
| Claude Code | Reads its own manifest format, so the InternKim host publishes a marketplace entry with `strict: false` that names `./skills` and `./mcp.json`: `claude plugin marketplace add yeomyeonggeori/internkim`, then `claude plugin install internkim@internkim`. |
| Pi | Ships no MCP client. The community extensions `pi-agent-plugins` (an Agent Plugins 1.0.0 client) and `pi-mcp-adapter` load the layout: `pi install npm:pi-mcp-adapter`, `pi install npm:pi-agent-plugins`, then place a checkout under `.pi/plugins/`. |
| Bluecollar | The ACP host passes the servers in `mcp.json` when it opens a session; the loop itself owns no tools. |

## Paths

Every terminal command writes `<skill>` where the skill's own directory belongs.
A host substitutes the directory it installed the skill into before the model
reads the instruction; a client that does not substitute should treat `<skill>`
as the directory holding that `SKILL.md`. Nothing here names a host layout.

## Validation

```bash
skills-ref validate skills/<name>
python3 -m unittest discover -s tests
```

Every skill passes the [Agent Skills](https://agentskills.io/specification)
reference validator. The unit tests hold the bundle to what it promises above:
the copies of `scripts/skill_runtime.py` in `office` and `dataroom` stay one
file, every `office` command runs a bundled script and every command a reference
names exists, every command answers with the result envelope, the paperwork
specs' JSON skeletons pass the renderer's schema, the deck scripts keep their
behavior, and nothing under `skills/` reads an environment variable named after
a host.

## License

[Apache-2.0](LICENSE).
