"""The Render start command must resolve the bot package from its root directory."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


class RenderEntrypointTests(unittest.TestCase):
    def test_bot_main_imports_from_render_root_directory(self):
        bot_directory = Path(__file__).resolve().parent / "bot"
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment["BOT_TOKEN"] = "123456:TEST_TOKEN"
        result = subprocess.run(
            [sys.executable, "-c", "import main; print('RENDER_IMPORT_OK')"],
            cwd=bot_directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RENDER_IMPORT_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
