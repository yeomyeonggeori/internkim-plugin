# internkim-plugin

Skills from the [InternKim](https://intern.kim) agent, packaged as an
[Agent Plugins](https://agent-plugins.org) 1.0.0 plugin so they run on any
conforming client.

Six need only a shell and Python.

| Skill | What it does |
| --- | --- |
| `pdf` | Builds and validates PDFs, including Korean typography |
| `spreadsheet` | Creates and edits `.xlsx` workbooks |
| `presentation` | Builds HTML decks and exports PPTX |
| `calculator` | Evaluates arithmetic exactly |
| `weather` | Reads Open-Meteo forecasts with a local cache |
| `internkim-api` | Reads and changes a company's internkim workspace over its public API |

Twelve also need InternKim's tool server, which `internkim-api` reaches. Each
declares what it calls in its own `tool-references`.

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
| `create-gws-file` | Creates Google Docs and Sheets, sends Gmail |
| `web-search` | Searches the public web and fetches pages |

## Requirements

Python 3 and [uv](https://docs.astral.sh/uv/) on `PATH`. A skill that bundles
scripts declares its own dependencies in `scripts/requirements.txt` and installs
them into an environment it creates on first use, so nothing has to be prepared
in advance. `website` also needs [Bun](https://bun.sh).

A host that already has a prepared interpreter can point the skills at it with
`BLUECLAW_BUILTIN_SKILLS_PYTHON`, and at a shared package cache with
`BLUECLAW_DEPENDENCY_CACHE`. Neither is required.

`internkim-api` also needs a personal access token in `INTERNKIM_TOKEN`, issued
from the account settings of the internkim web app. Its frontmatter `metadata`
says so machine-readably under `kim.intern.requires-environment`, so a host with
no token to give can leave the skill out of its agent's prompt instead of
offering one whose first call fails. Run its setup script once:

```bash
sh skills/internkim-api/scripts/store_token.sh
```

It reads the token from a hidden prompt, puts it in this computer's own secret
store — macOS Keychain, or libsecret on Linux — and appends the line that reads
it back to your shell profile:

```bash
export INTERNKIM_TOKEN="$(security find-generic-password -s internkim -a api -w)"
```

No file in this repository ever holds the token. The skill names no tool of its
own either: it reads the catalog and the input schemas from the API at run time,
so a tool added or renamed there needs no change here.

| Platform | Setup script |
| --- | --- |
| macOS | Run and verified: Keychain through `security`, profile line appended to `~/.zshrc` |
| Linux | Run and verified in a Debian container: libsecret through `secret-tool`, profile line appended to `~/.bashrc`. It needs a D-Bus session and an unlocked keyring, and says so rather than passing libsecret's own wording along when it finds neither |
| Windows | Not supported. The script is `sh` and neither store is there; set `INTERNKIM_TOKEN` however the machine keeps secrets |

`scripts/rotate_token.sh <name>` replaces a token that has been seen. It mints
the successor with the token it is replacing, checks the new one answers, stores
it, and only then revokes the old one, so a failure anywhere leaves the working
token in place. The new token goes from the API into the secret store without
being printed.

Two things the setup script does not solve. On macOS it passes the token to `security`
as an argument, which is visible in `ps` for as long as that call runs; the
manual page says as much about `-w`. And a shell profile is read by interactive
shells, so an agent started by systemd or a launcher sees nothing: give those the
variable through the unit or the launcher instead.

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
