import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "palworld_vars_mirror.py"


def server_payload(server_id, server_type):
    return {
        "id": server_id,
        "type": server_type,
        "data": {
            "port": {
                "type": "integer",
                "value": 8211,
            },
            "BaseCampMaxNumInGuild": {
                "type": "integer",
                "value": 5,
            },
            "bAllowGlobalPalboxExport": {
                "type": "boolean",
                "value": True,
            },
        },
    }


class MirrorDirectoryTests(unittest.TestCase):

    def test_servers_dir_mirrors_only_palworld_servers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            servers = root / "servers"
            servers.mkdir()

            pal_id = "pal12345"
            mc_id = "mc123456"

            (servers / pal_id).mkdir()
            (servers / mc_id).mkdir()

            (servers / f"{pal_id}.json").write_text(
                json.dumps(
                    server_payload(
                        pal_id,
                        "palworld",
                    )
                ),
                encoding="utf-8",
            )

            (servers / f"{mc_id}.json").write_text(
                json.dumps(
                    server_payload(
                        mc_id,
                        "minecraft",
                    )
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--servers-dir",
                    str(servers),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )

            pal_mirror = (
                servers
                / pal_id
                / ".pufferpanel-palworld-vars.json"
            )

            mc_mirror = (
                servers
                / mc_id
                / ".pufferpanel-palworld-vars.json"
            )

            self.assertTrue(
                pal_mirror.is_file()
            )

            self.assertFalse(
                mc_mirror.exists()
            )

            mirror = json.loads(
                pal_mirror.read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                mirror["server_id"],
                pal_id,
            )

            self.assertEqual(
                mirror["variables"][
                    "BaseCampMaxNumInGuild"
                ]["value"],
                5,
            )

    def test_servers_dir_ignores_unrelated_json_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            servers = root / "servers"
            servers.mkdir()

            (servers / "random.json").write_text(
                json.dumps(
                    {
                        "hello": "world"
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--servers-dir",
                    str(servers),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=result.stdout + result.stderr,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
