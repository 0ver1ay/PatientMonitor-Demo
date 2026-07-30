import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.config_loader import ConfigLoader


class ConfigLoaderHardeningTests(unittest.TestCase):
    def test_env_overrides_take_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            config_path.write_text(
                "[DATABASE]\nhost = file-host\nport = 1111\ndatabase = filedb\n"
                "user = fileuser\npassword = filepass\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "PATIENTMONITOR_DB_HOST": "env-host",
                    "PATIENTMONITOR_DB_PORT": "2222",
                    "PATIENTMONITOR_DB_NAME": "envdb",
                    "PATIENTMONITOR_DB_USER": "envuser",
                    "PATIENTMONITOR_DB_PASSWORD": "envpass",
                },
                clear=True,
            ):
                cfg = ConfigLoader(str(config_path))
                self.assertEqual(cfg.get_db_host(), "env-host")
                self.assertEqual(cfg.get_db_port(), 2222)
                self.assertEqual(cfg.get_db_name(), "envdb")
                self.assertEqual(cfg.get_db_user(), "envuser")
                self.assertEqual(cfg.get_db_password(), "envpass")

    def test_validate_database_settings_reports_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            config_path.write_text("[DATABASE]\nhost =\nport = 0\n", encoding="utf-8")
            cfg = ConfigLoader(str(config_path))
            issues = cfg.validate_database_settings(require_password=True)
            self.assertTrue(any("host" in item for item in issues))
            self.assertTrue(any("port" in item for item in issues))
            self.assertTrue(any("password" in item for item in issues))

    def test_prefers_config_local_ini_in_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.ini").write_text(
                "[DATABASE]\nhost = tracked\npassword =\n",
                encoding="utf-8",
            )
            (root / "config.local.ini").write_text(
                "[DATABASE]\nhost = local\npassword = secret\n",
                encoding="utf-8",
            )
            old = os.getcwd()
            try:
                os.chdir(root)
                cfg = ConfigLoader("config.ini")
                self.assertTrue(str(cfg.config_path).endswith("config.local.ini"))
                self.assertEqual(cfg.get_db_host(), "local")
                self.assertEqual(cfg.get_db_password(), "secret")
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
