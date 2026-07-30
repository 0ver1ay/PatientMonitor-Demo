"""
Общий пул подключений к базе данных для всех мониторов
"""
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict
import threading


class SharedDatabasePool:
    """Общий пул подключений к базе данных"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SharedDatabasePool, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.connection_pool = None
        self.config = None
        self.signal_names_cache = {}
        self._pool_lock = threading.RLock()
        self._initialized = True
    
    def initialize(self, host: str, port: int, database: str, user: str, password: str) -> bool:
        """Инициализировать общий пул и вернуть признак успеха."""
        requested_config = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        print(f"[SharedDatabasePool.initialize] Начало инициализации: {host}:{port}/{database}")

        with self._pool_lock:
            if self.connection_pool is not None:
                if self.config != requested_config:
                    raise RuntimeError(
                        "Общий пул уже подключен к другой конфигурации БД. "
                        "Перезапустите подключение перед применением нового config.ini."
                    )
                print("[SharedDatabasePool.initialize] Пул уже инициализирован, пропускаем")
                return True

            self.config = requested_config
            try:
                print("[SharedDatabasePool.initialize] Создание ThreadedConnectionPool...")
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password
                )
                print("[SharedDatabasePool.initialize] УСПЕХ! Создан общий пул подключений к БД: 2-10 соединений")
                return True
            except Exception as e:
                print(f"[SharedDatabasePool.initialize] ОШИБКА создания пула подключений: {e}")
                self.connection_pool = None
                self.config = None
                return False
    
    def get_connection(self):
        """Получить соединение из пула"""
        if self.connection_pool is None:
            return None
        
        try:
            return self.connection_pool.getconn()
        except Exception as e:
            print(f"Ошибка получения соединения из пула: {e}")
            return None
    
    def return_connection(self, conn):
        """Вернуть соединение в пул"""
        if self.connection_pool is None or conn is None:
            return
        
        try:
            self.connection_pool.putconn(conn)
        except Exception as e:
            print(f"Ошибка возврата соединения в пул: {e}")
    
    def close_all(self):
        """Закрыть общий пул один раз на границе жизненного цикла процесса."""
        with self._pool_lock:
            if self.connection_pool is None:
                return
            try:
                self.connection_pool.closeall()
                print("Общий пул подключений закрыт")
            except Exception as e:
                print(f"Ошибка закрытия пула: {e}")
            finally:
                self.connection_pool = None
                self.config = None
                self.signal_names_cache.clear()
    
    def get_signal_names_cache(self) -> Dict:
        """Получить кэш названий сигналов"""
        return self.signal_names_cache
    
    def set_signal_names_cache(self, cache: Dict):
        """Установить кэш названий сигналов"""
        self.signal_names_cache = cache






