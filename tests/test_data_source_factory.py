import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils.config_loader import ConfigLoader
from utils.data_generator import DataGenerator
from utils.data_source_factory import (
    create_configured_data_source,
    database_retry_delay,
)


class FakeDatabaseConfig:
    def get_mode(self):
        return "database"

    def get_db_host(self):
        return "db.local"

    def get_db_port(self):
        return 6000

    def get_db_name(self):
        return "med"

    def get_db_user(self):
        return "monitor"

    def get_db_password(self):
        return "secret"

    def get_signal_ids(self):
        return {"spo2": 76}


class DataSourceFactoryTests(unittest.TestCase):
    @patch("utils.data_source_factory.DatabaseDataSource")
    def test_database_failure_never_returns_generator(self, database_source_cls):
        database_source = MagicMock()
        database_source.is_available.return_value = False
        database_source_cls.return_value = database_source

        result = create_configured_data_source(FakeDatabaseConfig())

        self.assertEqual(result.mode, "database")
        self.assertFalse(result.available)
        self.assertIs(result.source, database_source)
        self.assertNotIsInstance(result.source, DataGenerator)
        self.assertIn("db.local:6000/med", result.error)

    def test_retry_delay_is_bounded(self):
        self.assertEqual(database_retry_delay(0), 5.0)
        self.assertEqual(database_retry_delay(1), 10.0)
        self.assertEqual(database_retry_delay(2), 30.0)
        self.assertEqual(database_retry_delay(100), 60.0)

    def test_demo_mode_requires_explicit_environment_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.ini"
            config_path.write_text("[DATABASE]\nmode = demo\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(ConfigLoader(str(config_path)).get_mode(), "database")
            with patch.dict(
                os.environ,
                {"PATIENTMONITOR_ALLOW_DEMO_MODE": "1"},
                clear=True,
            ):
                self.assertEqual(ConfigLoader(str(config_path)).get_mode(), "demo")


if __name__ == "__main__":
    unittest.main()
