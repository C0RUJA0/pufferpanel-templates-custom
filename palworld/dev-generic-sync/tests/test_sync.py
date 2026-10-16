import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "palworld_settings_sync.py"


DEFAULT_BODY = r'''[/Script/Pal.PalGameWorldSettings]
OptionSettings=(Difficulty=None,DayTimeSpeedRate=1.000000,ExpRate=1.000000,BaseCampMaxNumInGuild=4,bAllowGlobalPalboxExport=False,bAllowGlobalPalboxImport=False,ServerName="Default Palworld Server",ServerDescription="hello, world",DeathPenalty=All,ServerPassword="",AdminPassword="")
'''

ACTIVE_BODY = r'''[/Script/Pal.PalGameWorldSettings]
OptionSettings=(Difficulty=None,DayTimeSpeedRate=1.000000,ExpRate=1.000000,BaseCampMaxNumInGuild=4,bAllowGlobalPalboxExport=False,bAllowGlobalPalboxImport=False,ServerName="Meu Server",ServerDescription="descricao atual",DeathPenalty=All,ServerPassword="SEGREDO_EXISTENTE",AdminPassword="")
'''


def write_case(tmpdir: Path, variables: dict):
    default = tmpdir / "DefaultPalWorldSettings.ini"
    active = tmpdir / "PalWorldSettings.ini"
    mirror = tmpdir / ".pufferpanel-palworld-vars.json"

    default.write_text(DEFAULT_BODY, encoding="utf-8")
    active.write_text(ACTIVE_BODY, encoding="utf-8")

    mirror.write_text(
        json.dumps(
            {
                "schema": 1,
                "server_id": "test-palworld",
                "variables": variables,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    return default, active, mirror


def run_sync(default: Path, active: Path, mirror: Path):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--default",
            str(default),
            "--active",
            str(active),
            "--mirror",
            str(mirror),
        ],
        text=True,
        capture_output=True,
    )


class GenericSyncTests(unittest.TestCase):

    def test_boolean_integer_and_decimal_string(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "BaseCampMaxNumInGuild": {
                        "type": "integer",
                        "value": 5,
                    },
                    "bAllowGlobalPalboxExport": {
                        "type": "boolean",
                        "value": True,
                    },
                    "ExpRate": {
                        "type": "string",
                        "value": "2.5",
                    },
                },
            )

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            text = active.read_text(encoding="utf-8")

            self.assertIn("BaseCampMaxNumInGuild=5", text)
            self.assertIn("bAllowGlobalPalboxExport=True", text)
            self.assertIn("ExpRate=2.5", text)

    def test_quoted_string_is_safely_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "ServerName": {
                        "type": "string",
                        "value": 'Servidor "Coruja"',
                    },
                },
            )

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            text = active.read_text(encoding="utf-8")

            self.assertIn(
                r'ServerName="Servidor \"Coruja\""',
                text,
            )

    def test_bare_token_setting(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "DeathPenalty": {
                        "type": "string",
                        "value": "None",
                    },
                },
            )

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            text = active.read_text(encoding="utf-8")

            self.assertIn("DeathPenalty=None", text)

    def test_unknown_key_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "VariavelQueNaoExisteNoPalworld": {
                        "type": "integer",
                        "value": 999,
                    },
                },
            )

            before = active.read_bytes()

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            self.assertEqual(active.read_bytes(), before)

    def test_password_variables_are_denied_and_existing_password_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "ServerPassword": {
                        "type": "string",
                        "value": "NAO_PODE_ENTRAR",
                    },
                    "AdminPassword": {
                        "type": "string",
                        "value": "NAO_PODE_ENTRAR",
                    },
                    "bAllowGlobalPalboxImport": {
                        "type": "boolean",
                        "value": True,
                    },
                },
            )

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            text = active.read_text(encoding="utf-8")

            self.assertIn(
                'ServerPassword="SEGREDO_EXISTENTE"',
                text,
            )

            self.assertIn(
                'AdminPassword=""',
                text,
            )

            self.assertNotIn("NAO_PODE_ENTRAR", text)
            self.assertIn(
                "bAllowGlobalPalboxImport=True",
                text,
            )

    def test_existing_keys_are_not_duplicated(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "BaseCampMaxNumInGuild": {
                        "type": "integer",
                        "value": 7,
                    },
                    "bAllowGlobalPalboxExport": {
                        "type": "boolean",
                        "value": True,
                    },
                },
            )

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            text = active.read_text(encoding="utf-8")

            self.assertEqual(
                text.count("BaseCampMaxNumInGuild="),
                1,
            )

            self.assertEqual(
                text.count("bAllowGlobalPalboxExport="),
                1,
            )

    def test_unmanaged_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "ExpRate": {
                        "type": "string",
                        "value": "3.0",
                    },
                },
            )

            result = run_sync(default, active, mirror)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            text = active.read_text(encoding="utf-8")

            self.assertIn(
                'ServerDescription="descricao atual"',
                text,
            )

            self.assertIn(
                'ServerName="Meu Server"',
                text,
            )

            self.assertIn(
                "DayTimeSpeedRate=1.000000",
                text,
            )

    def test_invalid_numeric_value_fails_without_modifying_active_file(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)

            default, active, mirror = write_case(
                td,
                {
                    "ExpRate": {
                        "type": "string",
                        "value": "isso-nao-e-numero",
                    },
                },
            )

            before = active.read_bytes()

            result = run_sync(default, active, mirror)

            self.assertNotEqual(
                result.returncode,
                0,
                msg="invalid numeric value unexpectedly succeeded",
            )

            combined = (
                result.stdout + result.stderr
            ).lower()

            self.assertIn(
                "invalid",
                combined,
            )

            self.assertEqual(
                active.read_bytes(),
                before,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
