---
name: calculator
description: Calculate explicit arithmetic expressions exactly when the user asks a direct arithmetic question or provides an expression.
compatibility: Requires python3 and the ability to run a bundled script.
metadata:
  kim.intern.tool-references: "shell"
---


In every terminal command below, `<skill>` is this skill's own directory — the one holding this `SKILL.md`.

# Calculator

Use the bundled deterministic evaluator for precise results, large numbers, and multi-step arithmetic. Do not compute non-trivial arithmetic by hand.

For simple greetings or non-numeric explanations, answer directly without this skill.

## Workflow

1. Extract the exact arithmetic expression from the request.
2. Run the evaluator:

```json
{
  "command": "python3 <skill>/scripts/calc.py \"(2+3)*4\"",
  "workingDirectoryPath": "<skill>"
}
```

3. The script prints one JSON object on stdout. The `result` field is the answer to relay. Answer with the result only unless the user asks for explanation.

## Supported syntax

- numbers and decimals
- parentheses
- `+`, `-`, `*`, `/`, `%`
- `^` and `**` both mean power

## Unsupported syntax

- functions such as `sqrt(2)`
- variables and assignment
- text, file, network, or process access

On invalid input the script prints a one-line error to stderr and exits 1. Explain the limitation to the user instead of retrying the same expression.
