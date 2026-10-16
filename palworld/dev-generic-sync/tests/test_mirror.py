import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "palworld_vars_mirror.py"
FIXTURE = ROOT / "fixtures" / "6face996.json"


def run_mirror(server_json: Path, output_dir: Path):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--server-json",
            str(server_json),
            "--output-dir",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
    )


class MirrorTests(unittest.TestCase):

    def test_palworld_json_generates_typed_mirror(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)

            result = run_mirror(FIXTURE, out)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            target = out / ".pufferpanel-palworld-vars.json"
            self.assertTrue(target.is_file())

            data = json.loads(target.read_text(encoding="utf-8"))

            self.assertEqual(data["schema"], 1)
            self.assertEqual(data["server_id"], "6face996")

            variables = data["variables"]

            self.assertEqual(
                variables["BaseCampMaxNumInGuild"],
                {
                    "type": "integer",
                    "value": 5,
                },
            )

            self.assertEqual(
                variables["bAllowGlobalPalboxExport"],
                {
                    "type": "boolean",
                    "value": True,
                },
            )

            self.assertEqual(
                variables["bAllowGlobalPalboxImport"],
                {
                    "type": "boolean",
                    "value": True,
                },
            )

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            out1 = Path(td1)
            out2 = Path(td2)

            r1 = run_mirror(FIXTURE, out1)
            r2 = run_mirror(FIXTURE, out2)

            self.assertEqual(r1.returncode, 0, msg=r1.stdout + r1.stderr)
            self.assertEqual(r2.returncode, 0, msg=r2.stdout + r2.stderr)

            a = (out1 / ".pufferpanel-palworld-vars.json").read_bytes()
            b = (out2 / ".pufferpanel-palworld-vars.json").read_bytes()

            self.assertEqual(a, b)

    def test_non_palworld_server_is_ignored(self):
        original = json.loads(FIXTURE.read_text(encoding="utf-8"))
        original["type"] = "minecraft"

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fake = td / "server.json"
            out = td / "out"
            out.mkdir()

            fake.write_text(
                json.dumps(original),
                encoding="utf-8",
            )

            result = run_mirror(fake, out)

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            self.assertFalse(
                (out / ".pufferpanel-palworld-vars.json").exists()
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
