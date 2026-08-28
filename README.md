# run-model

Pick, configure, and run one local GGUF model.

## Setup

```bash
uv sync
```

Run either version through the uv environment:

```bash
uv run ./run-model         # SQLite
uv run ./run-model-json    # JSON
```

## Versions

| Command | Storage | Notes |
| --- | --- | --- |
| `./run-model` | `models.db` | SQLite storage with JSON import and export |
| `./run-model-json` | `models.json` | Human-readable JSON storage |

Both versions provide the same model selection, argument editor, and custom runner support.

The manager uses `fzf` when it is available. Otherwise, it shows a numbered menu.

## Commands

```bash
uv run ./run-model                  # Select and run a model
uv run ./run-model gemma            # Start with a search query
uv run ./run-model add              # Add a model
uv run ./run-model edit             # Edit a model
uv run ./run-model remove           # Remove a database entry
uv run ./run-model config           # Show the SQLite path
```

`remove` does not delete the GGUF file.

## Argument editor

`add` and `edit` open an embedded multiline editor.

| Key | Action |
| --- | --- |
| Arrow keys | Move the cursor |
| Enter | Add a line |
| F3 | Clear all arguments |
| Ctrl+S or F2 | Save |
| Ctrl+C | Cancel |

The manager passes the model as `-m MODEL`, followed by the saved arguments.

## SQLite JSON backup

```bash
uv run ./run-model export models.json
uv run ./run-model import models.json
uv run ./run-model import models.json --replace
```

Import rejects duplicate names. Use `--replace` to update matching models.

## Storage

The SQLite version stores settings in `models.db`. The JSON version uses `models.json`.

Both files stay beside their executable. Each model has a name, model path, runner path, and argument list.

## Test a runner

Use `test_runner` to inspect the exact command arguments:

```text
Runner: ./test_runner
```

Select that model through `run-model`. The test runner prints each received argument and exits.
