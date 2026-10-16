#!/usr/bin/env python3

import json
import sys
from pathlib import Path


DEV = Path(
    "/home/casa-os/pufferpanel-templates-custom/"
    "palworld/dev-generic-sync"
)

sys.path.insert(0, str(DEV))

from palworld_vars_mirror import mirror_server_json
from palworld_settings_sync import (
    _locate_option_settings,
    sync_settings,
)


ROOT = Path(__file__).resolve().parent

SERVER = ROOT / "6face996.json"
DEFAULT = ROOT / "DefaultPalWorldSettings.ini"
ACTIVE = ROOT / "PalWorldSettings.ini"


EXTRA_VARIABLES = {
    "ExpRate": {
        "type": "string",
        "value": "2.5",
    },
    "PalSpawnNumRate": {
        "type": "string",
        "value": "1.25",
    },
    "PalEggDefaultHatchingTime": {
        "type": "string",
        "value": "0.5",
    },
}


EXPECTED_EXISTING = {
    "BaseCampMaxNumInGuild": "5",
    "bAllowGlobalPalboxExport": "True",
    "bAllowGlobalPalboxImport": "True",
}


EXPECTED_EXTRA = {
    "ExpRate": "2.5",
    "PalSpawnNumRate": "1.25",
    "PalEggDefaultHatchingTime": "0.5",
}


def parse_settings(path):
    text = path.read_text(encoding="utf-8")
    _, info = _locate_option_settings(text)

    values = {}

    for item in info["entries"]:
        name = item["name"]

        if name in values:
            raise RuntimeError(
                f"duplicate key detected: {name}"
            )

        values[name] = item["token"]

    return values


print("========== VALIDANDO DEFAULT REAL ==========")

default_values = parse_settings(DEFAULT)

missing = [
    name
    for name in EXTRA_VARIABLES
    if name not in default_values
]

if missing:
    raise SystemExit(
        "SMOKE_ABORT_MISSING_DEFAULT_KEYS="
        + ",".join(missing)
    )

for name in EXTRA_VARIABLES:
    print(
        f"{name} default_token="
        f"{default_values[name]}"
    )

print("DEFAULT_KEYS_OK")


print()
print("========== ESTADO DA COPIA ANTES ==========")

before_values = parse_settings(ACTIVE)

server_password_before = before_values.get(
    "ServerPassword"
)

admin_password_before = before_values.get(
    "AdminPassword"
)

print(
    "ServerPassword definido antes =",
    bool(
        server_password_before
        and server_password_before != '""'
    ),
)

print(
    "AdminPassword definido antes =",
    bool(
        admin_password_before
        and admin_password_before != '""'
    ),
)


print()
print("========== ADICIONANDO VARIAVEIS SO NA COPIA ==========")

server = json.loads(
    SERVER.read_text(encoding="utf-8")
)

data = server.get("data")

if not isinstance(data, dict):
    raise SystemExit(
        "SMOKE_ABORT_SERVER_DATA_INVALID"
    )

for name, config in EXTRA_VARIABLES.items():
    data[name] = config

SERVER.write_text(
    json.dumps(
        server,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("COPIED_SERVER_JSON_PATCH_OK")


print()
print("========== GERANDO MIRROR ==========")

mirror_path = mirror_server_json(
    SERVER,
    ROOT,
)

if mirror_path is None:
    raise SystemExit(
        "SMOKE_ABORT_MIRROR_SKIPPED"
    )

mirror = json.loads(
    mirror_path.read_text(
        encoding="utf-8"
    )
)

for name in (
    "BaseCampMaxNumInGuild",
    "bAllowGlobalPalboxExport",
    "bAllowGlobalPalboxImport",
    "ExpRate",
    "PalSpawnNumRate",
    "PalEggDefaultHatchingTime",
):
    if name not in mirror["variables"]:
        raise SystemExit(
            f"SMOKE_ABORT_MIRROR_MISSING={name}"
        )

print(
    "mirror_variables =",
    len(mirror["variables"]),
)

print("MIRROR_REAL_COPY_OK")


print()
print("========== EXECUTANDO SYNC GENERICO ==========")

result = sync_settings(
    DEFAULT,
    ACTIVE,
    mirror_path,
)

print(
    "applied =",
    result["applied"],
)

print(
    "blocked =",
    result["blocked"],
)

print(
    "ignored =",
    result["ignored"],
)


print()
print("========== VALIDANDO RESULTADO ==========")

after_values = parse_settings(ACTIVE)

for name, expected in EXPECTED_EXISTING.items():
    actual = after_values.get(name)

    print(
        f"{name}={actual}"
    )

    if actual != expected:
        raise SystemExit(
            f"SMOKE_FAIL_EXISTING "
            f"{name}={actual!r} "
            f"expected={expected!r}"
        )


for name, expected in EXPECTED_EXTRA.items():
    actual = after_values.get(name)

    print(
        f"{name}={actual}"
    )

    if actual != expected:
        raise SystemExit(
            f"SMOKE_FAIL_EXTRA "
            f"{name}={actual!r} "
            f"expected={expected!r}"
        )


print()
print("========== SENHAS ==========")

server_password_after = after_values.get(
    "ServerPassword"
)

admin_password_after = after_values.get(
    "AdminPassword"
)

if server_password_after != server_password_before:
    raise SystemExit(
        "SMOKE_FAIL_SERVER_PASSWORD_CHANGED"
    )

if admin_password_after != admin_password_before:
    raise SystemExit(
        "SMOKE_FAIL_ADMIN_PASSWORD_CHANGED"
    )

print("ServerPassword preservado = True")
print("AdminPassword preservado  = True")


print()
print("========== CAMPOS NAO GERENCIADOS ==========")

managed = (
    set(EXPECTED_EXISTING)
    | set(EXPECTED_EXTRA)
)

for name, old_value in before_values.items():
    if name in managed:
        continue

    new_value = after_values.get(name)

    if new_value != old_value:
        raise SystemExit(
            f"SMOKE_FAIL_UNMANAGED_CHANGED={name}"
        )

print("UNMANAGED_SETTINGS_PRESERVED_OK")


print()
print("========== DUPLICATAS ==========")

if len(after_values) != len(
    set(after_values)
):
    raise SystemExit(
        "SMOKE_FAIL_DUPLICATE_KEYS"
    )

print("NO_DUPLICATE_KEYS_OK")


print()
print("========== TESTE DE IDEMPOTENCIA ==========")

first_bytes = ACTIVE.read_bytes()

second = sync_settings(
    DEFAULT,
    ACTIVE,
    mirror_path,
)

second_bytes = ACTIVE.read_bytes()

if second_bytes != first_bytes:
    raise SystemExit(
        "SMOKE_FAIL_SECOND_SYNC_CHANGED_FILE"
    )

print(
    "second_applied =",
    second["applied"],
)

print("IDEMPOTENT_SYNC_OK")


print()
print("PALWORLD_GENERIC_REAL_COPY_SMOKE_OK")
