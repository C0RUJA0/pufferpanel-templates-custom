#!/usr/bin/env python3

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path


BLOCKED_KEYS = {
    "ServerPassword",
    "AdminPassword",
}

SUPPORTED_TYPES = {
    "boolean",
    "integer",
    "string",
}

NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)

SAFE_BARE_RE = re.compile(
    r"^[A-Za-z0-9_.:+/-]+$"
)


def _split_top_level(text: str):
    """
    Divide OptionSettings por virgulas somente no nivel principal.

    Respeita:
    - strings entre aspas;
    - caracteres escapados;
    - (), [] e {} aninhados.
    """

    parts = []
    buf = []

    quote = False
    escaped = False
    stack = []

    pairs = {
        ")": "(",
        "]": "[",
        "}": "{",
    }

    for ch in text:
        if quote:
            buf.append(ch)

            if escaped:
                escaped = False

            elif ch == "\\":
                escaped = True

            elif ch == '"':
                quote = False

            continue

        if ch == '"':
            quote = True
            buf.append(ch)

        elif ch in "([{":
            stack.append(ch)
            buf.append(ch)

        elif ch in ")]}":
            if not stack or stack[-1] != pairs[ch]:
                raise ValueError(
                    "invalid OptionSettings nesting"
                )

            stack.pop()
            buf.append(ch)

        elif ch == "," and not stack:
            parts.append("".join(buf))
            buf = []

        else:
            buf.append(ch)

    if quote:
        raise ValueError(
            "invalid OptionSettings: unterminated quoted string"
        )

    if stack:
        raise ValueError(
            "invalid OptionSettings: unterminated nested value"
        )

    parts.append("".join(buf))

    return parts


def _parse_entry(raw: str):
    if "=" not in raw:
        raise ValueError(
            f"invalid OptionSettings entry: {raw!r}"
        )

    name, token = raw.split("=", 1)

    name = name.strip()
    token = token.strip()

    if not name:
        raise ValueError(
            "invalid OptionSettings entry: empty key"
        )

    return name, token


def _locate_option_settings(text: str):
    lines = text.splitlines(keepends=True)
    found = []

    for index, line in enumerate(lines):
        if line.endswith("\r\n"):
            newline = "\r\n"
            body = line[:-2]

        elif line.endswith("\n") or line.endswith("\r"):
            newline = line[-1]
            body = line[:-1]

        else:
            newline = ""
            body = line

        leading_len = len(body) - len(body.lstrip())
        leading = body[:leading_len]
        stripped = body[leading_len:]

        prefix = "OptionSettings=("

        if not stripped.startswith(prefix):
            continue

        if not stripped.endswith(")"):
            raise ValueError(
                "invalid OptionSettings line ending"
            )

        content = stripped[len(prefix):-1]

        raw_entries = _split_top_level(content)

        entries = []
        seen = set()

        for raw in raw_entries:
            name, token = _parse_entry(raw)

            if name in seen:
                raise ValueError(
                    f"duplicate OptionSettings key: {name}"
                )

            seen.add(name)

            entries.append(
                {
                    "raw": raw,
                    "name": name,
                    "token": token,
                }
            )

        found.append(
            {
                "index": index,
                "leading": leading,
                "newline": newline,
                "entries": entries,
            }
        )

    if len(found) != 1:
        raise ValueError(
            "expected exactly one OptionSettings line, "
            f"found {len(found)}"
        )

    return lines, found[0]


def _classify_default(token: str):
    if token in {"True", "False"}:
        return "boolean"

    if NUMBER_RE.fullmatch(token):
        return "number"

    if (
        len(token) >= 2
        and token[0] == '"'
        and token[-1] == '"'
    ):
        return "quoted"

    if SAFE_BARE_RE.fullmatch(token):
        return "bare"

    return "complex"


def _normalize_value(
    name: str,
    config: dict,
    default_token: str,
):
    if not isinstance(config, dict):
        raise ValueError(
            f"invalid variable definition for {name}"
        )

    declared_type = config.get("type")

    if declared_type not in SUPPORTED_TYPES:
        raise ValueError(
            f"invalid variable type for "
            f"{name}: {declared_type!r}"
        )

    if "value" not in config:
        raise ValueError(
            f"invalid variable definition for "
            f"{name}: missing value"
        )

    value = config["value"]
    kind = _classify_default(default_token)

    if kind == "boolean":
        if (
            declared_type != "boolean"
            or type(value) is not bool
        ):
            raise ValueError(
                f"invalid boolean value for {name}"
            )

        return "True" if value else "False"

    if kind == "number":
        if declared_type == "integer":
            if type(value) is not int:
                raise ValueError(
                    f"invalid integer value for {name}"
                )

            return str(value)

        if (
            declared_type == "string"
            and type(value) is str
        ):
            candidate = value.strip()

            if not NUMBER_RE.fullmatch(candidate):
                raise ValueError(
                    f"invalid numeric value for {name}"
                )

            return candidate

        raise ValueError(
            f"invalid numeric value for {name}"
        )

    if kind == "quoted":
        if (
            declared_type != "string"
            or type(value) is not str
        ):
            raise ValueError(
                f"invalid string value for {name}"
            )

        if "\n" in value or "\r" in value:
            raise ValueError(
                f"invalid multiline string value for {name}"
            )

        escaped_value = (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        return f'"{escaped_value}"'

    if kind == "bare":
        if (
            declared_type != "string"
            or type(value) is not str
        ):
            raise ValueError(
                f"invalid bare value for {name}"
            )

        candidate = value.strip()

        if not SAFE_BARE_RE.fullmatch(candidate):
            raise ValueError(
                f"invalid bare value for {name}"
            )

        return candidate

    raise ValueError(
        f"unsupported default value syntax for {name}"
    )


def _atomic_write_text(
    path: Path,
    text: str,
):
    st = path.stat()

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )

    tmp = Path(tmp_name)

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
            newline="",
        ) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

        os.chmod(
            tmp,
            stat.S_IMODE(st.st_mode),
        )

        # Quando executado como root no container,
        # preserva uid/gid do INI original.
        if os.geteuid() == 0:
            os.chown(
                tmp,
                st.st_uid,
                st.st_gid,
            )

        os.replace(
            tmp,
            path,
        )

    finally:
        if tmp.exists():
            tmp.unlink()


def sync_settings(
    default_path: Path,
    active_path: Path,
    mirror_path: Path,
):
    default_path = Path(default_path)
    active_path = Path(active_path)
    mirror_path = Path(mirror_path)

    default_text = default_path.read_text(
        encoding="utf-8"
    )

    active_text = active_path.read_text(
        encoding="utf-8"
    )

    mirror = json.loads(
        mirror_path.read_text(
            encoding="utf-8"
        )
    )

    if (
        not isinstance(mirror, dict)
        or mirror.get("schema") != 1
    ):
        raise ValueError(
            "invalid mirror schema"
        )

    variables = mirror.get("variables")

    if not isinstance(variables, dict):
        raise ValueError(
            "invalid mirror variables"
        )

    _, default_info = _locate_option_settings(
        default_text
    )

    active_lines, active_info = (
        _locate_option_settings(
            active_text
        )
    )

    defaults = {
        item["name"]: item["token"]
        for item in default_info["entries"]
    }

    replacements = {}

    blocked = 0
    ignored = 0

    # Primeiro valida TUDO.
    # So depois alteramos o arquivo.
    for name in sorted(variables):
        if name in BLOCKED_KEYS:
            blocked += 1
            continue

        # Inclui automaticamente coisas como "port":
        # nao existe em OptionSettings -> ignorado.
        if name not in defaults:
            ignored += 1
            continue

        replacements[name] = _normalize_value(
            name,
            variables[name],
            defaults[name],
        )

    changed = 0
    rebuilt = []

    for item in active_info["entries"]:
        name = item["name"]

        if name not in replacements:
            # Preserva texto original de campos nao gerenciados.
            rebuilt.append(
                item["raw"]
            )
            continue

        new_token = replacements[name]

        if item["token"] == new_token:
            rebuilt.append(
                item["raw"]
            )
            continue

        rebuilt.append(
            f"{name}={new_token}"
        )

        changed += 1

    new_line = (
        active_info["leading"]
        + "OptionSettings=("
        + ",".join(rebuilt)
        + ")"
        + active_info["newline"]
    )

    active_lines[
        active_info["index"]
    ] = new_line

    new_text = "".join(active_lines)

    # Muito importante:
    # se nada mudou, nem regravamos o INI.
    if new_text != active_text:
        _atomic_write_text(
            active_path,
            new_text,
        )

    return {
        "applied": changed,
        "blocked": blocked,
        "ignored": ignored,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Apply mirrored PufferPanel variables "
            "to Palworld settings."
        )
    )

    parser.add_argument(
        "--default",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--active",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--mirror",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    try:
        result = sync_settings(
            args.default,
            args.active,
            args.mirror,
        )

    except Exception as exc:
        # Nunca imprime valores das variaveis.
        print(
            f"SYNC_ERROR: {exc}",
            file=sys.stderr,
        )

        return 1

    print(
        "SYNC_OK "
        f"applied={result['applied']} "
        f"blocked={result['blocked']} "
        f"ignored={result['ignored']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
