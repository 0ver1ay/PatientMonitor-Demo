import unittest
from unittest.mock import MagicMock, patch

from utils.database_source import DatabaseDataSource
from utils.shared_db_pool import SharedDatabasePool


class SharedPoolLifecycleTests(unittest.TestCase):
    def setUp(self):
        SharedDatabasePool._instance = None

    def tearDown(self):
        instance = SharedDatabasePool._instance
        if instance is not None:
            instance.close_all()
        SharedDatabasePool._instance = None

    @patch("utils.shared_db_pool.psycopg2.pool.ThreadedConnectionPool")
    def test_closing_one_source_does_not_close_shared_pool(self, pool_factory):
        shared_pool = MagicMock()
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        shared_pool.getconn.return_value = connection
        pool_factory.return_value = shared_pool

        first = DatabaseDataSource(password="test")
        second = DatabaseDataSource(password="test")

        first.close()

        self.assertIsNone(first.connection_pool)
        self.assertIs(second.connection_pool, shared_pool)
        self.assertTrue(second.is_available())
        shared_pool.closeall.assert_not_called()

        SharedDatabasePool().close_all()
        shared_pool.closeall.assert_called_once_with()

    def test_private_pool_is_closed_by_its_owner(self):
        private_pool = MagicMock()
        source = DatabaseDataSource.__new__(DatabaseDataSource)
        source.connection_pool = private_pool
        source._pool_kind = "private"
        source._closed = False

        source.close()
        source.close()

        private_pool.closeall.assert_called_once_with()
        self.assertIsNone(source.connection_pool)


class GetBedInfoTests(unittest.TestCase):
    def _make_source(self, row):
        connection_pool = MagicMock()
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        connection.cursor.return_value = cursor
        connection_pool.getconn.return_value = connection

        source = DatabaseDataSource.__new__(DatabaseDataSource)
        source.connection_pool = connection_pool
        source.bed_id = None
        source._pool_kind = "shared"
        source._closed = False
        return source, connection_pool, connection, cursor

    def test_missing_bed_returns_none_without_fallback_queries(self):
        source, connection_pool, _connection, cursor = self._make_source(None)

        result = source.get_bed_info(999999)

        self.assertIsNone(result)
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertIn("FROM bed", cursor.execute.call_args.args[0])
        connection_pool.putconn.assert_called_once()

    def test_existing_bed_returns_compatible_identifiers(self):
        row = {
            "bed_id": 7,
            "bed_name": "Кровать 7",
            "bed_numb": "7",
            "room_id": 2,
            "block_id": 3,
            "status_id": 1,
            "patient_id": 11,
        }
        source, _connection_pool, _connection, cursor = self._make_source(row)

        result = source.get_bed_info(7)

        self.assertEqual(result["bed_id"], 7)
        self.assertEqual(result["id"], 7)
        self.assertEqual(result["name"], "Кровать 7")
        cursor.execute.assert_called_once()
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

    def test_uses_current_bed_when_argument_is_omitted(self):
        source, _connection_pool, _connection, cursor = self._make_source(
            {"bed_id": 4, "bed_name": "Кровать 4"}
        )
        source.bed_id = 4

        source.get_bed_info()

        self.assertEqual(cursor.execute.call_args.args[1], (4,))


if __name__ == "__main__":
    unittest.main()
