# Wrapper

The wrapper replaces commands such as `uv run ./run-model-json add` with `run add`.

## Create the wrapper

Create `run` in the project directory:

```bash
#!/usr/bin/env bash
ROOT=$(dirname "$(readlink -f "$0")")
exec uv run --project "$ROOT" "$ROOT/run-model-json" "$@"
```

Make it executable:

```bash
chmod +x run
```

Use it from the project directory:

```bash
./run
./run add
./run edit
./run remove
./run gemma
```

## Use it from any directory

Make sure that `~/.local/bin` is in your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to your shell configuration to keep the change.

Create a symlink:

```bash
mkdir -p ~/.local/bin
ln -s "$PWD/run" ~/.local/bin/run
```

You can now run:

```bash
run add
run edit
run gemma
```

The wrapper uses `readlink -f`, so it finds the project through the symlink.

## Select the storage version

The example wrapper starts the JSON version:

```bash
exec uv run --project "$ROOT" "$ROOT/run-model-json" "$@"
```

Use this line for SQLite:

```bash
exec uv run --project "$ROOT" "$ROOT/run-model" "$@"
```
