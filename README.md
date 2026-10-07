<p align="center">
  <img src="https://intern.kim/logo.svg" alt="" width="160">
</p>

<h1 align="center">internkim-plugin</h1>

<p align="center">
  The <a href="https://intern.kim">InternKim</a> agent's skills, in the coding agent you already use.
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/github/license/yeomyeonggeori/internkim-plugin?color=0E59B3">
  <img alt="Agent Plugins 1.0.0" src="https://img.shields.io/badge/Agent%20Plugins-1.0.0-0E59B3">
  <img alt="Claude Code and Codex" src="https://img.shields.io/badge/client-Claude%20Code%20%7C%20Codex-0E59B3">
</p>

## Overview

InternKim is an agent that works inside a company. It keeps the tasks, the
calendar, the data room and the mail, and it writes the documents. This plugin
gives Claude Code or Codex the same skills, so the agent on your own machine
can do that work too.

```text
> Make a quote for 박예시 from last week's meeting notes, on our
  letterhead, and add a task to send it on Friday.
```

It works as you. Every tool call carries your account, and your company's
permissions decide what it may do. Some skills, such as `calculator`,
`weather` and most of `office`, run on your machine and need no account. Each skill's
`SKILL.md` under [`skills/`](skills) says when it applies and which tools it
calls.

## Install

### Claude Code

```sh
claude plugin marketplace add yeomyeonggeori/internkim-plugin
claude plugin install internkim@internkim
```

### Codex

```sh
codex plugin marketplace add yeomyeonggeori/internkim-plugin
codex plugin add internkim@internkim
```

### Update

```sh
claude plugin marketplace update internkim
claude plugin update internkim@internkim
```

In Codex, `codex plugin marketplace upgrade` refreshes the catalog. A new
version applies from the next session.

### If you added the server by hand

The plugin declares the tool server itself. If `internkim` is already in your
MCP configuration, remove that entry, or every tool shows up twice:

```sh
claude mcp remove internkim -s user
```

## Sign in

There is nothing to configure. The `internkim` server shows as needing sign-in
until the first tool call, which opens intern.kim in the browser. The client
keeps the token, and the plugin never holds one. Until your account belongs to
a company, every tool answers `403` and says why.

## Requirements

Python 3 and [uv](https://docs.astral.sh/uv/) on `PATH`. For `office`, also
[Bun](https://bun.sh) or Node 18 or later, which draws pages without a
browser. A skill that needs packages names its setup command the first time,
and the agent runs it.

## Documentation

How the tool server signs you in, how each client loads the plugin, and what
the skills install are in [DOCS.md](DOCS.md). Using InternKim itself is at
<https://docs.intern.kim/plugin>.

## Contributing

```sh
python3 -m unittest discover -s tests
```

A pull request that changes what an installed copy does also raises `version`
in `plugin.json`. Clients cache a plugin under its version, so a change
without one never reaches anyone who already installed.

## License

[Apache-2.0](LICENSE), except the Paperlogy fonts under
`skills/office/assets/fonts/paperlogy/`, which are under the
[SIL Open Font License 1.1](skills/office/assets/fonts/paperlogy/OFL-1.1.txt).
