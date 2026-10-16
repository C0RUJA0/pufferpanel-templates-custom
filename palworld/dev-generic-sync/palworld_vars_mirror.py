#!/usr/bin/env python3

import argparse
import json
import os
import tempfile
from pathlib import Path


SUPPORTED_TYPES = {
    "boolean",
    "integer",
    "string",
}

BLOCKED_KEYS = {
    "ServerPassword",
    "AdminPassword",
}

MIRROR_NAME = ".pufferpanel-palworld-vars.json"


def _validate_value(
    name,
    declared_type,
    value,
):
    if declared_type == "boolean":
        if type(value) is not bool:
            raise ValueError(
                f"{name}: expected boolean, "
                f"got {type(value).__name__}"
            )

    elif declared_type == "integer":
        if type(value) is not int:
            raise ValueError(
                f"{name}: expected integer, "
                f"got {type(value).__name__}"
            )

    elif declared_type == "string":
        if type(value) is not str:
            raise ValueError(
                f"{name}: expected string, "
                f"got {type(value).__name__}"
            )


def _atomic_write_json(
    path: Path,
    payload: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        ) as f:
            json.dump(
                payload,
                f,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )

            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(
            tmp,
            path,
        )

    finally:
        if tmp.exists():
            tmp.unlink()


def mirror_server_json(
    source_json: Path,
    destination_dir: Path,
):
    source_json = Path(source_json)
    destination_dir = Path(
        destination_dir
    )

    with source_json.open(
        "r",
        encoding="utf-8",
    ) as f:
        server = json.load(f)

    if not isinstance(server, dict):
        raise ValueError(
            "server JSON root must be an object"
        )

    if server.get("type") != "palworld":
        return None

    server_id = server.get("id")

    if (
        not isinstance(server_id, str)
        or not server_id
    ):
        server_id = source_json.stem

    raw_data = server.get(
        "data",
        {},
    )

    if not isinstance(raw_data, dict):
        raise ValueError(
            "server data must be an object"
        )

    variables = {}

    for name, config in raw_data.items():
        if name in BLOCKED_KEYS:
            continue

        if not isinstance(config, dict):
            continue

        declared_type = config.get(
            "type"
        )

        if declared_type not in SUPPORTED_TYPES:
            continue

        if "value" not in config:
            continue

        value = config["value"]

        _validate_value(
            name,
            declared_type,
            value,
        )

        variables[name] = {
            "type": declared_type,
            "value": value,
        }

    payload = {
        "schema": 1,
        "server_id": server_id,
        "variables": variables,
    }

    target = (
        destination_dir
        / MIRROR_NAME
    )

    _atomic_write_json(
        target,
        payload,
    )

    return target


def mirror_servers_dir(
    servers_dir: Path,
):
    servers_dir = Path(
        servers_dir
    )

    if not servers_dir.is_dir():
        raise ValueError(
            f"servers directory does not exist: "
            f"{servers_dir}"
        )

    mirrored = []
    skipped = 0

    for source_json in sorted(
        servers_dir.glob("*.json")
    ):
        destination_dir = (
            servers_dir
            / source_json.stem
        )

        target = mirror_server_json(
            source_json,
            destination_dir,
        )

        if target is None:
            skipped += 1
            continue

        mirrored.append(
            target
        )

    return {
        "mirrored": mirrored,
        "skipped": skipped,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Mirror PufferPanel Palworld "
            "variables."
        )
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--server-json",
        type=Path,
        help=(
            "Process one PufferPanel "
            "server JSON."
        ),
    )

    mode.add_argument(
        "--servers-dir",
        type=Path,
        help=(
            "Scan a PufferPanel servers "
            "directory."
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        help=(
            "Destination directory when "
            "using --server-json."
        ),
    )

    args = parser.parse_args()

    if args.server_json is not None:
        if args.output_dir is None:
            parser.error(
                "--output-dir is required "
                "with --server-json"
            )

        target = mirror_server_json(
            args.server_json,
            args.output_dir,
        )

        if target is None:
            print(
                "SKIP_NON_PALWORLD"
            )

        else:
            print(
                f"MIRROR_OK path={target}"
            )

        return 0

    if args.output_dir is not None:
        parser.error(
            "--output-dir cannot be used "
            "with --servers-dir"
        )

    result = mirror_servers_dir(
        args.servers_dir
    )

    print(
        "MIRROR_SCAN_OK "
        f"mirrored={len(result['mirrored'])} "
        f"skipped={result['skipped']}"
    )

    for target in result["mirrored"]:
        print(
            f"MIRROR_OK path={target}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
