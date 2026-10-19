import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maintenance.refresh_audit import RefreshConfig, refresh


class RefreshAuditTests(unittest.TestCase):
    def test_refresh_only_runs_configured_generator_with_read_only_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generator = root / "generator.py"
            generator.write_text("# test generator", encoding="utf-8")
            codex_home = root / "codex"
            codex_home.mkdir()
            audit_dir = root / "audit"
            config = RefreshConfig(root, generator, audit_dir, codex_home)

            with patch("maintenance.refresh_audit.subprocess.run") as run:
                refresh(config)

            self.assertTrue(audit_dir.is_dir())
            run.assert_called_once()
            command, kwargs = run.call_args.args[0], run.call_args.kwargs
            self.assertEqual(command[:2], [sys.executable, str(generator)])
            self.assertEqual(kwargs["env"]["CODEX_HOME"], str(codex_home))
            self.assertEqual(kwargs["env"]["CODEX_AUDIT_OUT"], str(audit_dir))
            self.assertEqual(kwargs["cwd"], str(generator.parent))
            status = (audit_dir / "refresh_status.json").read_text(encoding="utf-8")
            self.assertIn('"state": "ok"', status)

    def test_refresh_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            generator = root / "generator.py"
            generator.write_text("# test generator", encoding="utf-8")
            config = RefreshConfig(root, generator, root / "audit", root / "missing")
            with self.assertRaises(FileNotFoundError):
                refresh(config)


if __name__ == "__main__":
    unittest.main()
