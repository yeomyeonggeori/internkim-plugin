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

`internkim-api` also needs a personal access token in `INTERNKIM_TOKEN`, issued
from the account settings of the internkim web app. Run its setup script once:

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

Two things the script does not solve. On macOS it passes the token to `security`
as an argument, which is visible in `ps` for as long as that call runs; the
manual page says as much about `-w`. And a shell profile is read by interactive
shells, so an agent started by systemd or a launcher sees nothing: give those the
variable through the unit or the launcher instead.

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
