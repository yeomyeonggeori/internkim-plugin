# internkim-plugin

The plugin is the portable [Agent Plugins](https://agent-plugins.org) 1.0.0
layout: `plugin.json`, `skills/` and `mcp.json`. The README says how to
install it; this page is the reference behind that.

## Skills

Each `SKILL.md` names the tools it calls in its frontmatter, under
`metadata.kim.intern.tool-references`. `bash` and `read` there are the
client's own shell and file reading, and every other name is a tool on
InternKim's server, so a skill that names only those two runs on the machine
alone. `office` is both: it makes and checks files locally, and calls the
server only to fill a company form on letterhead.

## Tool server

`mcp.json` declares `https://api.intern.kim/v1/mcp`, a Streamable HTTP server
that answers with the tools the signed-in member may use in their company. The
plugin carries no credential. The server follows MCP authorization: a request
without a token is answered `401` with a `WWW-Authenticate` header pointing at
its protected resource metadata, and a client that implements it signs the
member in through the browser and keeps the token itself.

A client that does not implement MCP authorization can send a personal access
token, issued from the account settings of the InternKim web app, as
`Authorization: Bearer ik_…`. Configure that in the client; this repository
never holds one.

## Loading it

The plugin carries no client-specific manifest or adapter. The repository also
publishes itself as a marketplace, through one catalog per client that points
at the plugin and adds nothing to it.

| Client | How it loads the plugin |
| --- | --- |
| Codex | `.agents/plugins/marketplace.json` lists the repository root, and Codex reads `plugin.json`, `skills/` and `mcp.json` there natively (openai/codex#36544). |
| Claude Code | `.claude-plugin/marketplace.json` lists the repository root with `strict: false`, naming `./skills` and `./mcp.json`, because Claude Code reads its own manifest format. |
| Pi | Ships no MCP client. The community extensions `pi-agent-plugins` (an Agent Plugins 1.0.0 client) and `pi-mcp-adapter` load the layout: `pi install npm:pi-mcp-adapter`, `pi install npm:pi-agent-plugins`, then place a checkout under `.pi/plugins/`. |
| [Bluecollar](https://github.com/yeomyeonggeori/bluecollar) | The ACP host passes the servers in `mcp.json` when it opens a session; the loop itself owns no tools. |

Both Claude Code and Codex cache an installed plugin under its version, so a
copy is replaced only when `version` in `plugin.json` changes.

## Setup

A skill that bundles scripts declares its Python packages in
`scripts/requirements.txt` and reads them from an environment prepared once,
ahead of use: `scripts/office setup` for `office`, where `--with-ocr` adds the
OCR engine, and `python3 scripts/skill_runtime.py setup` for the others.
InternKim's host install runs these. Elsewhere the agent runs them the first
time a command asks. No other command installs anything; one whose
environment is missing names the setup to run.

Setup installs into the skill directory itself, each piece beside the code
that reads it and pinned by a committed lock: `pylock.toml` for Python, which
the command in its header compiles from `requirements.txt`, and
`package-lock.json` for the renderer. `office setup` prints where each piece
went. A piece installed from an older lock counts as missing, so setup after an
update rebuilds what changed and a command never runs against a stale one.
Commands only read these pieces, so a requester who cannot write to the skill
directory can still use it. A host with a shared package cache points
`UV_CACHE_DIR` at it, and the skills read no variable named after the host
that runs them.

## Office

`office` runs every command through one entry, `scripts/office <format>
<verb>`, and `scripts/office --help` lists the commands. Each command prints one
JSON result with a status and coded issues, and `scripts/office guide <format>`
prints the fields every input takes and every code a command reports, generated
from the validators themselves. [`skills/office/DOCS.md`](skills/office/DOCS.md)
covers the rest.

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
reference validator. The unit tests hold the bundle to what this page
promises: the copies of `scripts/skill_runtime.py` in `office` and `dataroom`
stay one file, every `office` command runs a bundled script and every command
a reference names exists, every command answers with the result envelope,
`doc apply` changes a file all at once or not at all and leaves the parts it
does not edit byte-identical, the paperwork specs' JSON skeletons pass the
renderer's schema, the deck scripts keep their behavior, and nothing under
`skills/` reads an environment variable named after a host.
