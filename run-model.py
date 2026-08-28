#!/usr/bin/env python3
"""Select, configure, and run local models."""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "models.json"
DEFAULT_RUNNER = "./llama-cpp-new/build/bin/llama-server"
DEFAULT_ARGS = (
    "--host 0.0.0.0 --port 8888 --temp 0.6 --top-p 0.95 --top-k 20 "
    "--min-p 0.0 --presence-penalty 0.0 --repeat-penalty 1.0 -c 65536"
)


def select(options, prompt, query=""):
    if not options:
        return None

    if fzf := shutil.which("fzf"):
        command = [fzf, "--height=80%", "--layout=reverse", "--border", "--prompt", prompt]
        if query:
            command += ["--query", query]
        result = subprocess.run(command, input="\n".join(options), text=True, stdout=subprocess.PIPE, cwd=ROOT)
        return result.stdout.rstrip("\n") or None

    matches = [item for item in options if query.casefold() in item.casefold()]
    if len(matches) == 1:
        return matches[0]
    options = matches or options
    for number, item in enumerate(options, 1):
        print(f"{number:>3}  {item}")
    try:
        answer = input(f"{prompt.strip()} number: ").strip()
        return options[int(answer) - 1] if answer else None
    except (EOFError, KeyboardInterrupt, ValueError, IndexError):
        return None


def ask(label, default=""):
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(130)


def format_arguments(arguments):
    lines = []
    for argument in arguments:
        quoted = shlex.quote(argument)
        if argument.startswith("-") or not lines:
            lines.append(quoted)
        else:
            lines[-1] += f" {quoted}"
    return "\n".join(lines)


def edit_arguments(arguments):
    try:
        from prompt_toolkit import prompt
        from prompt_toolkit.key_binding import KeyBindings
    except ImportError:
        raise SystemExit("Install dependencies with: uv sync")

    bindings = KeyBindings()

    @bindings.add("c-s")
    @bindings.add("f2")
    def save(event):
        event.app.exit(result=event.app.current_buffer.text)

    @bindings.add("f3")
    def clear(event):
        event.app.current_buffer.text = ""

    @bindings.add("c-c")
    def cancel(event):
        event.app.exit(result=None)

    text = format_arguments(arguments)
    error_message = ""
    while True:
        text = prompt(
            "Server arguments\n> ",
            default=text,
            multiline=True,
            key_bindings=bindings,
            prompt_continuation=lambda width, line_number, is_soft_wrap: "... ",
            bottom_toolbar=lambda: error_message or "Arrows move | Enter new line | F3 clear | Ctrl+S/F2 save | Ctrl+C cancel",
            mouse_support=True,
        )
        if text is None:
            return None
        try:
            return shlex.split(text)
        except ValueError as error:
            error_message = f"Invalid arguments: {error}"


def validate_models(models):
    if not isinstance(models, list):
        raise ValueError("JSON must contain a list of models")

    names = set()
    expected_fields = {"name", "model", "runner", "args"}
    for index, model in enumerate(models, 1):
        valid = (
            isinstance(model, dict)
            and expected_fields.issubset(set(model))
            and all(isinstance(model[field], str) and model[field] for field in ("name", "model", "runner"))
            and isinstance(model["args"], list)
            and all(isinstance(argument, str) for argument in model["args"])
        )
        if not valid:
            raise ValueError(f"invalid model at position {index}")
        name = model["name"].casefold()
        if name in names:
            raise ValueError(f"duplicate model name {model['name']!r}")
        names.add(name)
    return models


def load_models():
    if not DATABASE.exists():
        return []
    try:
        with DATABASE.open("r") as f:
            models = json.load(f)
        validate_models(models)
        for i, model in enumerate(models):
            model['id'] = i
        return models
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Cannot read {DATABASE}: {error}")


def save_models(models):
    save_list = [
        {field: model[field] for field in ("name", "model", "runner", "args")}
        for model in models
    ]
    temporary = DATABASE.with_name(f".{DATABASE.name}.tmp")
    try:
        temporary.write_text(json.dumps(save_list, indent=2) + "\n")
        temporary.replace(DATABASE)
    except OSError as error:
        raise SystemExit(f"Cannot write {DATABASE}: {error}")


def add_model(arguments):
    parser = argparse.ArgumentParser(prog="run-model add", description="Add a model to models.json.")
    parser.add_argument("model", nargs="?", help="GGUF model path")
    parser.add_argument("--name", help="display name")
    parser.add_argument("--runner", help="server executable")
    parser.add_argument("--args", dest="server_args", help="quoted server arguments")
    args = parser.parse_args(arguments)

    model_path = args.model
    if not model_path:
        models_dir = Path(os.environ.get("RUN_MODEL_MODELS", "/models"))
        try:
            paths = sorted((str(path) for path in models_dir.glob("*.gguf")), key=str.casefold)
        except OSError:
            paths = []
        model_path = select(paths, "model > ") if paths else None
        model_path = model_path or ask("Model path")

    name = (args.name or ask("Name", Path(model_path).stem)).strip()
    if not name:
        print("Name cannot be empty.", file=sys.stderr)
        return 2

    runner = args.runner or ask("Runner", DEFAULT_RUNNER)
    try:
        parsed_args = (
            shlex.split(args.server_args)
            if args.server_args is not None
            else edit_arguments(shlex.split(DEFAULT_ARGS))
        )
    except ValueError as error:
        print(f"Invalid server arguments: {error}", file=sys.stderr)
        return 2
    if parsed_args is None:
        return 130

    existing_models = load_models()
    for m in existing_models:
        if m["name"].casefold() == name.casefold():
            print(f"A model named {name!r} already exists in {DATABASE}", file=sys.stderr)
            return 2

    existing_models.append({
        "name": name,
        "model": model_path,
        "runner": runner,
        "args": parsed_args
    })

    try:
        save_models(existing_models)
    except SystemExit as e:
        print(f"Add failed: {e}", file=sys.stderr)
        return 2

    print(f"Added {name!r} to {DATABASE}")
    return 0


def remove_model(query=""):
    models = load_models()
    if not models:
        print(f"No models in {DATABASE}.", file=sys.stderr)
        return 1

    labels = {f"{model['name']}  {model['model']}": model for model in models}
    selected = select(list(labels), "remove > ", query)
    if not selected:
        return 0

    model = labels[selected]
    try:
        confirmed = input(f"Remove {model['name']!r} from the database? [y/N]: ").strip().casefold()
    except (EOFError, KeyboardInterrupt):
        print()
        return 130
    if confirmed not in {"y", "yes"}:
        print("Cancelled.")
        return 0

    models = [m for m in models if m["name"].casefold() != model["name"].casefold()]

    try:
        save_models(models)
    except SystemExit as e:
        print(f"Remove failed: {e}", file=sys.stderr)
        return 2

    print(f"Removed {model['name']!r}. Model file was not deleted.")
    return 0


def run(query=""):
    models = load_models()
    if not models:
        print(f"No models in {DATABASE}. Add one with: ./run-model add", file=sys.stderr)
        return 1

    labels = {f"{model['name']}  {model['model']}": model for model in models}
    selected = select(list(labels), "model > ", query)
    if not selected:
        return 0

    model = labels[selected]
    command = [model["runner"], "-m", model["model"], *model["args"]]
    os.chdir(ROOT)
    try:
        os.execvp(command[0], command)
    except OSError as error:
        print(f"Cannot start {command[0]}: {error}", file=sys.stderr)
        return 126


def edit_model(query=""):
    models = load_models()
    if not models:
        print(f"No models in {DATABASE}. Add one with: ./run-model add", file=sys.stderr)
        return 1

    labels = {f"{model['name']}  {model['model']}": model for model in models}
    selected = select(list(labels), "edit > ", query)
    if not selected:
        return 0

    model = labels[selected]
    print("Press Enter to keep the current value.")
    name = ask("Name", model["name"]).strip()
    if not name:
        print("Name cannot be empty.", file=sys.stderr)
        return 2
    model_path = ask("Model path", model["model"])
    runner = ask("Runner", model["runner"])
    parsed_args = edit_arguments(model["args"])
    if parsed_args is None:
        return 130

    if name.casefold() != model["name"].casefold():
        for m in models:
            if m["name"].casefold() == name.casefold() and m["id"] != model["id"]:
                print(f"A model named {name!r} already exists in {DATABASE}", file=sys.stderr)
                return 2

    model["name"] = name
    model["model"] = model_path
    model["runner"] = runner
    model["args"] = parsed_args

    try:
        save_models(models)
    except SystemExit as e:
        print(f"Edit failed: {e}", file=sys.stderr)
        return 2

    print(f"Updated {name!r}")
    return 0


def self_test():
    args = shlex.split("--port 8888 --flash-attn on")

    tmp_path = ROOT / ".test_models.json"
    if tmp_path.exists():
        tmp_path.unlink()

    global DATABASE
    old_db = DATABASE
    DATABASE = tmp_path

    try:
        save_models([{
            "name": "My Model",
            "model": "/models/My Model.gguf",
            "runner": "./llama server",
            "args": args,
        }])

        models = load_models()
        assert len(models) == 1
        row = models[0]
        assert [row["runner"], "-m", row["model"], *row["args"]] == [
            "./llama server", "-m", "/models/My Model.gguf", "--port", "8888", "--flash-attn", "on"
        ]

        try:
            validate_models([{
                "name": "My Model",
                "model": "/models/My Model.gguf",
                "runner": "./llama server",
                "args": args,
            }, {
                "name": "my model",
                "model": "/models/My Model2.gguf",
                "runner": "./llama server",
                "args": args,
            }])
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate JSON names should fail validation")

        print("self-test passed")
        return 0
    finally:
        DATABASE = old_db
        if tmp_path.exists():
            tmp_path.unlink()


def main():
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "add":
        return add_model(arguments[1:])
    if arguments == ["config"]:
        print(DATABASE)
        return 0
    if arguments and arguments[0] == "edit":
        return edit_model(" ".join(arguments[1:]))
    if arguments and arguments[0] in {"remove", "del"}:
        return remove_model(" ".join(arguments[1:]))
    if arguments == ["--self-test"]:
        return self_test()
    if arguments and arguments[0] in {"-h", "--help"}:
        print(
            "Usage: run-model [SEARCH]\n"
            "       run-model add [MODEL] [--name NAME] [--runner PATH] [--args '...']\n"
            "       run-model edit [SEARCH]\n"
            "       run-model remove [SEARCH]\n"
            "       run-model config"
        )
        return 0
    return run(" ".join(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
