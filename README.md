# internkim-plugin

Skills from the [InternKim](https://intern.kim) agent, packaged as an
[Agent Plugins](https://agent-plugins.org) 1.0.0 plugin so they run on any
conforming client.

Six run on their own with a shell and Python.

| Skill | What it does |
| --- | --- |
| `pdf` | Builds and validates PDFs, including Korean typography |
| `spreadsheet` | Creates and edits `.xlsx` workbooks |
| `presentation` | Builds HTML decks and exports PPTX |
| `calculator` | Evaluates arithmetic exactly |
| `weather` | Reads Open-Meteo forecasts with a local cache |
| `dataroom` | Files, checks and searches a company data room, locally or in the record |

Eleven call InternKim's tool server, the `internkim` server that `mcp.json`
declares. Each names the tools it calls in its own `tool-references`.

| Skill | What it does |
| --- | --- |
| `internkim-task` | Adds, finds, updates and completes work items |
| `calendar` | Adds, lists, changes and removes calendar events |
| `scheduled-task` | Schedules work to run later or repeatedly |
| `direct-message` | Sends and schedules direct messages |
| `messages` | Reads, posts, edits and removes conversation messages |
| `mail` | Connects a mailbox, then reads, searches and sends mail |
| `document` | Authors `.docx` and PDF from a Markdown source |
| `paperwork` | Fills standardized company forms and contracts on letterhead |
| `website` | Scaffolds, builds, previews and publishes a site |
| `company-data` | Reads and records company profile, metrics and records |
| `web-search` | Searches the public web and fetches pages |

## Requirements

Python 3 and [uv](https://docs.astral.sh/uv/) on `PATH`. A skill that bundles
scripts declares its own dependencies in `scripts/requirements.txt` and installs
them into an environment it creates on first use, so nothing has to be prepared
in advance. `website` also needs [Bun](https://bun.sh).

A host that already has a prepared interpreter can point the skills at it with
`BLUECLAW_BUILTIN_SKILLS_PYTHON`, and at a shared package cache with
`BLUECLAW_DEPENDENCY_CACHE`. Neither is required.

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

## Claude Code

Claude Code reads the generated `.claude-plugin/plugin.json` identity manifest
and `.mcp.json` transport manifest. Validate a checkout with:

```bash
claude plugin validate .
```

To use a local checkout for a session, run `claude --plugin-dir /path/to/internkim-plugin`.
The plugin keeps the same shared
`skills/` directory and MCP server; it does not add a second skill copy.

## Pi

The generated root `package.json` carries Pi’s package metadata. Its `pi`
section points at the shared `./skills` directory and the local extension at
`./adapters/pi/index.ts`. From a checkout, install the package dependencies and
run the adapter checks with:

```bash
bun install
bun run check
bun test tests/pi
```

From the project where you want to use it, run `pi install -l /path/to/internkim-plugin`.
This records the local package in that project's `.pi/settings.json`. The extension registers
`internkim_tools`, which lists the server catalog when called with `names: []`
and loads requested tools by their exact canonical names. Loaded tools use the
`internkim__<tool-name>` prefix. File, shell, and other native client tools
remain owned by Pi; the extension only supplies the InternKim MCP tools.

The extension uses the server URL in `mcp.json`. Set
`INTERNKIM_MCP_URL` to override it, and set `INTERNKIM_MCP_BEARER_TOKEN` when
the client supplies a bearer credential through the environment. This adapter
does not perform browser sign-in or refresh tokens; supply a personal access
token or a credential managed by the host running Pi.

### Opt-in live MCP evaluation

To exercise Pi's model loop, tool discovery, and schema-driven invocation
against a harmless loopback fixture, set an explicit OpenRouter model and run:

```bash
OPENROUTER_API_KEY=... PI_EVAL_MODEL=... \
  bun evals/pi-mcp-live.ts --evidence-dir /tmp/internkim-pi-evidence
```

The evaluation uses isolated temporary Pi state, limits tool calls and runtime,
and writes the transcript, usage, and fixture call evidence to
`<evidence-dir>/pi-mcp-live.json`. It is opt-in and makes no parity or
performance claim about other models or environments.

## Paths

Every terminal command writes `<skill>` where the skill's own directory belongs.
A host substitutes the directory it installed the skill into before the model
reads the instruction; a client that does not substitute should treat `<skill>`
as the directory holding that `SKILL.md`. Nothing here names a host layout.

## Validation

```bash
skills-ref validate skills/<name>
```

Every skill passes the [Agent Skills](https://agentskills.io/specification)
reference validator.

## License

[Apache-2.0](LICENSE).
