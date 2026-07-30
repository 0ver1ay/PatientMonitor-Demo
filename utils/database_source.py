"""
Источник данных из PostgreSQL базы данных
"""
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from utils.data_source import DataSource
from typing import Optional, List, Dict, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseDataSource(DataSource):
    """
    Источник данных из PostgreSQL базы данных
    
    Подключается к базе med, таблицы signals и bed связаны по bed_id.
    Получает значения из поля signals_value каждую секунду для выбранной кровати.
    """

    @classmethod
    def disconnected(
        cls,
        host: str = "localhost",
        port: int = 6000,
        database: str = "med",
        user: str = "postgres",
        signal_ids: dict | None = None,
        bed_id: Optional[int] = None,
    ) -> "DatabaseDataSource":
        """Создать безопасный offline-источник без попытки подключения."""
        instance = cls.__new__(cls)
        instance.host = host
        instance.port = port
        instance.database = database
        instance.user = user
        instance.password = ""
        instance.signal_ids = signal_ids or {
            "spo2": 76,
            "pulse": 77,
            "breathing": 50,
            "temperature": 57,
        }
        instance.bed_id = bed_id
        instance.signal_names_cache = {}
        instance.connection_pool = None
        instance._pool_kind = "none"
        instance._closed = False
        instance._initialized = False
        return instance
    
    def __init__(self, host: str = 'localhost', port: int = 6000, 
                 database: str = 'med', user: str = 'postgres', 
                 password: str = '', signal_ids: dict = None, bed_id: Optional[int] = None):
        """
        Инициализация источника данных из БД
        
        Args:
            host: Хост PostgreSQL
            port: Порт PostgreSQL (по умолчанию 6000)
            database: Имя базы данных (med)
            user: Имя пользователя
            password: Пароль
            signal_ids: Словарь с signal_id для каждого параметра
                       {'spo2': 76, 'pulse': 77, 'breathing': 50, 'temperature': 57}
            bed_id: ID кровати для фильтрации данных (None - первая доступная)
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        
        # Маппинг signal_id для каждого параметра
        self.signal_ids = signal_ids or {
            'spo2': 76,
            'pulse': 77,
            'breathing': 50,
            'temperature': 57
        }
        
        # ID текущей выбранной кровати
        self.bed_id = bed_id
        
        # Кэш названий сигналов из таблицы signal_param
        self.signal_names_cache = {}
        
        # Пул соединений для эффективной работы
        self.connection_pool = None
        self._pool_kind = "none"
        self._closed = False
        self._initialized = False
        self._connect()
        
        # Ленивая инициализация - не загружаем данные сразу
        # Данные будут загружены при первом обращении
    
    def _connect(self):
        """Создание подключения к базе данных - использует общий пул"""
        self._closed = False
        self._pool_kind = "none"
        print(f"[DatabaseDataSource._connect] Попытка подключения к БД: {self.host}:{self.port}/{self.database}")
        try:
            # Пытаемся использовать общий пул подключений
            from utils.shared_db_pool import SharedDatabasePool
            shared_pool = SharedDatabasePool()
            print(f"[DatabaseDataSource._connect] SharedDatabasePool получен, connection_pool = {shared_pool.connection_pool is not None}")
            
            print(f"[DatabaseDataSource._connect] Инициализация общего пула подключений...")
            initialized = shared_pool.initialize(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            print(f"[DatabaseDataSource._connect] Пул инициализирован: {initialized}")
            
            # Используем общий пул
            self.connection_pool = shared_pool.connection_pool
            
            if self.connection_pool:
                self._pool_kind = "shared"
                # Проверяем подключение
                print(f"[DatabaseDataSource._connect] Проверка подключения...")
                conn = self.connection_pool.getconn()
                if conn:
                    self.connection_pool.putconn(conn)
                    print(f"[DatabaseDataSource._connect] Подключение успешно! Используется общий пул подключений к БД {self.database} на порту {self.port}")
                    logger.info(f"Используется общий пул подключений к БД {self.database} на порту {self.port}")
                else:
                    print(f"[DatabaseDataSource._connect] ОШИБКА: Не удалось получить соединение из пула")
            else:
                print(f"[DatabaseDataSource._connect] ОШИБКА: connection_pool = None после инициализации")
                raise ConnectionError("Не удалось инициализировать общий пул подключений")
        except Exception as e:
            print(f"[DatabaseDataSource._connect] ИСКЛЮЧЕНИЕ при использовании общего пула: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"Ошибка подключения к базе данных: {e}")
            # Fallback - создаем свой пул
            try:
                print(f"[DatabaseDataSource._connect] Попытка создать отдельный пул подключений...")
                self.connection_pool = None
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 5,
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password
                )
                self._pool_kind = "private"
                print(f"[DatabaseDataSource._connect] Отдельный пул создан успешно!")
                logger.info(f"Создан отдельный пул подключений к БД {self.database}")
            except Exception as e2:
                print(f"[DatabaseDataSource._connect] ОШИБКА создания отдельного пула: {e2}")
                import traceback
                traceback.print_exc()
                logger.error(f"Ошибка создания пула подключений: {e2}")
                self.connection_pool = None
                self._pool_kind = "none"
    
    def _load_signal_names(self):
        """Загрузка названий сигналов из таблицы signal_param"""
        if not self.connection_pool:
            return
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Загружаем названия для всех используемых signal_id
            signal_ids_list = list(self.signal_ids.values())
            if not signal_ids_list:
                return
            
            # Формируем запрос для получения названий сигналов
            placeholders = ','.join(['%s'] * len(signal_ids_list))
            query = f"""
                SELECT signal_id, signal_descr_rus 
                FROM signal_param 
                WHERE signal_id IN ({placeholders})
            """
            
            conn.rollback()  # Откатываем на случай предыдущей ошибки
            cursor.execute(query, signal_ids_list)
            results = cursor.fetchall()
            conn.commit()  # Коммитим успешный запрос
            cursor.close()
            
            # Сохраняем в кэш
            for row in results:
                signal_id = row.get('signal_id')
                signal_name = row.get('signal_descr_rus', '')
                if signal_id is not None:
                    self.signal_names_cache[signal_id] = signal_name
                    logger.debug(f"Загружено название сигнала: signal_id={signal_id}, name={signal_name}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки названий сигналов: {e}")
            if conn:
                conn.rollback()  # Откатываем при ошибке
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def get_signal_name(self, signal_id: int) -> str:
        """
        Получить название сигнала из таблицы signal_param по signal_id
        
        Args:
            signal_id: ID сигнала
            
        Returns:
            str: Название сигнала из колонки signal_descr_rus или пустая строка
        """
        return self.signal_names_cache.get(signal_id, '')
    
    def get_signal_name_by_key(self, param_key: str) -> str:
        """
        Получить название сигнала по ключу параметра (spo2, pulse, breathing, temperature)
        
        Args:
            param_key: Ключ параметра ('spo2', 'pulse', 'breathing', 'temperature')
            
        Returns:
            str: Название сигнала из БД или значение по умолчанию
        """
        signal_id = self.signal_ids.get(param_key)
        if signal_id:
            name = self.get_signal_name(signal_id)
            if name:
                return name
        
        # Значения по умолчанию, если не найдено в БД
        defaults = {
            'spo2': 'SPO2',
            'pulse': 'Пульс',
            'breathing': 'Дыхание',
            'temperature': 'Температура'
        }
        return defaults.get(param_key, 'Параметр')
    
    def get_value(self, signal_id: int) -> Optional[float]:
        """
        Универсальный метод получения значения параметра по signal_id
        
        Args:
            signal_id: ID сигнала из таблицы signal_param
            
        Returns:
            Optional[float]: Значение параметра или None
        """
        return self._get_latest_value(signal_id)
    
    def get_available_signals(self, include_inactive: bool = False) -> List[Dict]:
        """
        Получить список всех доступных сигналов из таблицы signal_param
        
        Returns:
            List[Dict]: Список словарей с информацией о сигналах
                       [{'signal_id': 1, 'name': 'SPO2', 'unit': '%', 'min': 90, 'max': 100}, ...]
        """
        # Ленивая инициализация
        self._ensure_initialized()
        
        if not self.connection_pool:
            logger.warning("Нет подключения к базе данных")
            return []
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Получаем все доступные сигналы из таблицы signal_param
            if include_inactive:
                query = """
                    SELECT signal_id, signal_descr_rus, signal_unit, signal_min, signal_max
                    FROM signal_param
                    ORDER BY signal_id ASC
                """
            else:
                query = """
                    SELECT signal_id, signal_descr_rus, signal_unit, signal_min, signal_max
                    FROM signal_param
                    WHERE status_param = 1 OR status_param IS NULL
                    ORDER BY signal_id ASC
                """
            
            conn.rollback()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.commit()
            cursor.close()
            
            signals = []
            for row in results:
                signal_id = row.get('signal_id')
                if signal_id is not None:
                    db_min = row.get('signal_min')
                    db_max = row.get('signal_max')
                    signal_info = {
                        'signal_id': signal_id,
                        'name': row.get('signal_descr_rus', f'Сигнал {signal_id}'),
                        'unit': row.get('signal_unit', ''),
                        'min': db_min if db_min is not None else 0.0,
                        'max': db_max if db_max is not None else 100.0,
                        'db_min': db_min,
                        'db_max': db_max,
                    }
                    signals.append(signal_info)
            
            logger.info(f"Загружено доступных сигналов: {len(signals)}")
            return signals
            
        except Exception as e:
            logger.error(f"Ошибка получения списка сигналов: {e}")
            if conn:
                conn.rollback()
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def update_signal_display_ranges(self, ranges: List[Dict]) -> int:
        """Записать signal_min/signal_max в signal_param по списку диапазонов."""
        self._ensure_initialized()
        if not self.connection_pool:
            logger.warning("Нет подключения к базе данных")
            return 0

        conn = None
        updated = 0
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor()
            conn.rollback()
            for item in ranges or []:
                try:
                    signal_id = int(item["signal_id"])
                    min_value = float(item["min"])
                    max_value = float(item["max"])
                except Exception:
                    continue
                if max_value <= min_value:
                    min_value, max_value = max_value, min_value
                cursor.execute(
                    """
                    UPDATE signal_param
                    SET signal_min = %s, signal_max = %s
                    WHERE signal_id = %s
                    """,
                    (min_value, max_value, signal_id),
                )
                updated += int(cursor.rowcount or 0)
            conn.commit()
            cursor.close()
            logger.info("Обновлено диапазонов signal_param: %s", updated)
            return updated
        except Exception as e:
            logger.error(f"Ошибка обновления signal_min/signal_max: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def _check_table_structure(self, table_name: str) -> dict:
        """
        Проверить структуру таблицы для диагностики
        
        Args:
            table_name: Имя таблицы
            
        Returns:
            dict: Информация о структуре таблицы
        """
        if not self.connection_pool:
            return {}
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Получаем информацию о колонках таблицы
            # Пробуем разные варианты запросов
            queries = [
                # Вариант 1: Стандартный запрос
                """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """,
                # Вариант 2: С указанием схемы
                """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                """,
                # Вариант 3: С кавычками
                """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = LOWER(%s)
                    ORDER BY ordinal_position
                """
            ]
            
            columns = None
            for query in queries:
                try:
                    conn.rollback()
                    cursor.execute(query, (table_name.lower(),))
                    columns = cursor.fetchall()
                    conn.commit()
                    if columns:
                        break
                except Exception as e:
                    logger.debug(f"Запрос структуры не сработал: {e}")
                    conn.rollback()
                    continue
            
            if not columns:
                # Последняя попытка без lower
                try:
                    conn.rollback()
                    cursor.execute(queries[0], (table_name,))
                    columns = cursor.fetchall()
                    conn.commit()
                except:
                    conn.rollback()
            
            cursor.close()
            
            if columns:
                return {
                    'columns': [col.get('column_name') for col in columns],
                    'types': {col.get('column_name'): col.get('data_type') for col in columns},
                    'nullable': {col.get('column_name'): col.get('is_nullable') for col in columns},
                    'defaults': {col.get('column_name'): col.get('column_default') for col in columns},
                    'full_info': [dict(col) for col in columns]
                }
            return {}
        except Exception as e:
            logger.error(f"Ошибка проверки структуры таблицы {table_name}: {e}")
            if conn:
                conn.rollback()
            return {}
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def check_all_tables_structure(self):
        """
        Проверить структуру всех используемых таблиц и вывести информацию
        """
        print("\n" + "="*60)
        print("ПРОВЕРКА СТРУКТУРЫ ТАБЛИЦ БД")
        print("="*60)
        
        tables = ['bed', 'signals', 'signal_param']
        
        for table_name in tables:
            print(f"\n--- Таблица: {table_name} ---")
            structure = self._check_table_structure(table_name)
            
            if structure:
                print(f"Колонки ({len(structure['columns'])}):")
                for col in structure['full_info']:
                    col_name = col.get('column_name', '?')
                    col_type = col.get('data_type', '?')
                    nullable = col.get('is_nullable', '?')
                    default = col.get('column_default', 'NULL')
                    print(f"  - {col_name}: {col_type} (nullable: {nullable}, default: {default})")
            else:
                print(f"  [ERROR] Таблица '{table_name}' не найдена или недоступна")
        
        print("\n" + "="*60 + "\n")
    
    def _ensure_initialized(self):
        """Обеспечить инициализацию данных (ленивая загрузка)"""
        if self._initialized:
            return
        
        # Загружаем названия сигналов из БД
        self._load_signal_names()
        
        # Если bed_id не указан, выбираем первую доступную кровать
        if self.bed_id is None:
            beds = self.get_available_beds()
            if beds:
                self.bed_id = beds[0]['id']
                logger.info(f"Автоматически выбрана кровать с ID: {self.bed_id}")
        
        self._initialized = True
    
    def get_available_beds(self) -> List[Dict]:
        """
        Получить список всех доступных кроватей из таблицы bed
        
        Returns:
            List[Dict]: Список словарей с информацией о кроватях [{'id': 1, 'name': 'Кровать 1'}, ...]
        """
        if not self.connection_pool:
            logger.warning("Нет подключения к базе данных")
            print("ОШИБКА: Нет подключения к базе данных (connection_pool = None)")
            return []
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Пробуем разные варианты запросов для совместимости
            # В таблице bed используется bed_id (не id!), bed_name, нет description
            queries = [
                # Вариант 1: Стандартный запрос с bed_id, bed_name и room_id
                """
                    SELECT bed_id, bed_name, room_id 
                    FROM bed 
                    ORDER BY bed_id ASC
                """,
                # Вариант 2: С кавычками для регистра
                """
                    SELECT "bed_id", "bed_name", "room_id" 
                    FROM "bed" 
                    ORDER BY "bed_id" ASC
                """,
                # Вариант 3: Все колонки таблицы
                """
                    SELECT * 
                    FROM bed 
                    ORDER BY bed_id ASC
                """
            ]
            
            results = None
            last_error = None
            
            for i, query in enumerate(queries):
                try:
                    # Делаем rollback перед каждым новым запросом на случай ошибки в предыдущем
                    conn.rollback()
                    cursor.execute(query)
                    results = cursor.fetchall()
                    conn.commit()  # Коммитим успешный запрос
                    logger.debug(f"Запрос успешен! Найдено кроватей: {len(results)}")
                    break
                except Exception as query_error:
                    last_error = query_error
                    error_msg = str(query_error)
                    logger.debug(f"Запрос {i+1} не сработал: {error_msg}")
                    conn.rollback()  # Откатываем транзакцию при ошибке
                    continue
            
            if results is None:
                conn.rollback()  # Откатываем перед выходом
                raise Exception(f"Все варианты запросов не сработали. Последняя ошибка: {last_error}")
            
            cursor.close()
            
            beds = []
            for row in results:
                # В таблице bed используется bed_id (не id!), bed_name, room_id
                bed_id = (row.get('bed_id') or row.get('BED_ID') or row.get('Bed_Id') or 
                         row.get('id') or row.get('ID'))  # fallback на id для совместимости
                bed_name = (row.get('bed_name') or row.get('BED_NAME') or row.get('Bed_Name') or 
                           row.get('name') or row.get('NAME') or row.get('Name'))
                room_id = (row.get('room_id') or row.get('ROOM_ID') or row.get('Room_Id') or 
                          row.get('room') or row.get('ROOM') or 0)
                
                if bed_id is not None:
                    bed_info = {
                        'id': bed_id,
                        'name': bed_name if bed_name else f'Кровать {bed_id}',
                        'room_id': room_id if room_id is not None else 0,
                        'description': ''  # Колонки description нет в таблице
                    }
                    beds.append(bed_info)
                    logger.debug(f"Добавлена кровать: id={bed_id}, name={bed_info['name']}, room_id={bed_info['room_id']}")
            
            logger.info(f"Всего загружено кроватей: {len(beds)}")
            
            return beds
                
        except Exception as e:
            error_msg = f"Ошибка получения списка кроватей: {e}"
            logger.error(error_msg)
            if conn:
                conn.rollback()  # Откатываем транзакцию при ошибке
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def set_bed_id(self, bed_id: int):
        """
        Установить ID кровати для фильтрации данных
        
        Args:
            bed_id: ID кровати
        """
        self.bed_id = bed_id
        logger.info(f"Выбрана кровать с ID: {bed_id}")
    
    def get_current_bed_id(self) -> Optional[int]:
        """
        Получить ID текущей выбранной кровати
        
        Returns:
            Optional[int]: ID кровати или None
        """
        return self.bed_id
    
    def _get_latest_value(self, signal_id: int) -> Optional[float]:
        """
        Получить последнее значение signals_value для указанного signal_id и bed_id
        
        Args:
            signal_id: ID сигнала из таблицы signal_param (SPO2, дыхание и т.д.)
            
        Returns:
            float: Последнее значение или None при ошибке
        """
        # Ленивая инициализация
        self._ensure_initialized()
        
        if not self.connection_pool:
            logger.warning("Нет подключения к базе данных")
            return None
        
        if self.bed_id is None:
            logger.warning("Не выбрана кровать (bed_id = None)")
            return None
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Запрос последнего значения из таблицы signals с фильтрацией по bed_id и signal_id
            # Получаем значение за последние 10 секунд, чтобы брать свежие данные
            queries = [
                # Вариант 1: С signals_date_time за последние 10 секунд
                """
                    SELECT signals_value, signals_date_time
                    FROM signals 
                    WHERE signal_id = %s AND bed_id = %s
                      AND (signals_date_time >= NOW() - INTERVAL '10 seconds' OR signals_date_time IS NULL)
                    ORDER BY signals_date_time DESC NULLS LAST, signals_id DESC
                    LIMIT 1
                """,
                # Вариант 2: Без фильтра по времени, просто последнее значение
                """
                    SELECT signals_value, signals_date_time
                    FROM signals 
                    WHERE signal_id = %s AND bed_id = %s
                    ORDER BY signals_date_time DESC NULLS LAST, signals_id DESC
                    LIMIT 1
                """,
                # Вариант 3: Просто по signals_id (если signals_date_time NULL)
                """
                    SELECT signals_value, signals_date_time
                    FROM signals 
                    WHERE signal_id = %s AND bed_id = %s
                    ORDER BY signals_id DESC 
                    LIMIT 1
                """
            ]
            
            result = None
            for query in queries:
                try:
                    conn.rollback()
                    cursor.execute(query, (signal_id, self.bed_id))
                    result = cursor.fetchone()
                    conn.commit()
                    if result:
                        break
                except Exception as query_error:
                    logger.debug(f"Запрос не сработал, пробуем следующий: {query_error}")
                    conn.rollback()
                    continue
            
            if not result:
                # Последняя попытка - простой запрос по signals_id
                try:
                    conn.rollback()
                    query = """
                        SELECT signals_value 
                        FROM signals 
                        WHERE signal_id = %s AND bed_id = %s
                        ORDER BY signals_id DESC 
                        LIMIT 1
                    """
                    cursor.execute(query, (signal_id, self.bed_id))
                    result = cursor.fetchone()
                    conn.commit()
                except:
                    conn.rollback()
            
            cursor.close()
            
            if result and 'signals_value' in result:
                value = result['signals_value']
                timestamp = result.get('signals_date_time')
                
                if value is not None:
                    float_value = float(value)
                    # Возвращаем значение даже если оно старое - лучше показать последние доступные данные
                    return float_value
                else:
                    logger.warning(f"Значение NULL для signal_id={signal_id}, bed_id={self.bed_id}")
                    return None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения значения для signal_id={signal_id}, bed_id={self.bed_id}: {e}")
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def get_spo2(self) -> float:
        """
        Получить значение SPO2 из базы данных
        
        Returns:
            float: Значение SPO2 или 0.0 при ошибке
        """
        signal_id = self.signal_ids.get('spo2')
        if not signal_id:
            logger.error("Не указан signal_id для SPO2")
            return 0.0
        
        value = self._get_latest_value(signal_id)
        # Возвращаем None вместо 0.0, чтобы можно было отличить отсутствие данных от нулевого значения
        return value if value is not None else None
    
    def get_pulse(self) -> float:
        """
        Получить значение пульса из базы данных
        
        Returns:
            float: Значение пульса или None при ошибке
        """
        signal_id = self.signal_ids.get('pulse')
        if not signal_id:
            logger.error("Не указан signal_id для пульса")
            return None
        
        value = self._get_latest_value(signal_id)
        return value
    
    def get_breathing(self) -> float:
        """
        Получить значение дыхания из базы данных
        
        Returns:
            float: Значение дыхания или None при ошибке
        """
        signal_id = self.signal_ids.get('breathing')
        if not signal_id:
            logger.error("Не указан signal_id для дыхания")
            return None
        
        value = self._get_latest_value(signal_id)
        return value
    
    def get_temperature(self) -> float:
        """
        Получить значение температуры из базы данных
        
        Returns:
            float: Значение температуры или None при ошибке
        """
        signal_id = self.signal_ids.get('temperature')
        if not signal_id:
            logger.error("Не указан signal_id для температуры")
            return None
        
        value = self._get_latest_value(signal_id)
        return value
    
    def is_available(self) -> bool:
        """Проверка доступности подключения к БД"""
        print(f"[DatabaseDataSource.is_available] Проверка доступности: connection_pool = {self.connection_pool is not None}")
        if not self.connection_pool:
            print(f"[DatabaseDataSource.is_available] connection_pool = None, возвращаем False")
            return False
        
        conn = None
        cursor = None
        healthy = False
        try:
            print(f"[DatabaseDataSource.is_available] Попытка получить соединение из пула...")
            conn = self.connection_pool.getconn()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                healthy = True
                print(f"[DatabaseDataSource.is_available] Соединение и запрос SELECT 1 выполнены успешно!")
                print(f"[DatabaseDataSource.is_available] Возвращаем True")
                return True
            else:
                print(f"[DatabaseDataSource.is_available] Не удалось получить соединение")
        except Exception as e:
            print(f"[DatabaseDataSource.is_available] ИСКЛЮЧЕНИЕ при проверке: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    self.connection_pool.putconn(conn, close=not healthy)
                except TypeError:
                    self.connection_pool.putconn(conn)
                except Exception:
                    pass
        
        print(f"[DatabaseDataSource.is_available] Возвращаем False")
        return False
    
    def get_historical_data(self, signal_id: int, hours: int = 6) -> List[tuple]:
        """
        Получить исторические данные для указанного signal_id и bed_id
        
        Args:
            signal_id: ID сигнала из таблицы signal_param
            hours: Количество часов истории (по умолчанию 6)
            
        Returns:
            List[tuple]: Список кортежей (value, timestamp) или пустой список
        """
        if not self.connection_pool:
            logger.warning("Нет подключения к базе данных")
            return []
        
        if self.bed_id is None:
            logger.warning("Не выбрана кровать (bed_id = None)")
            return []
        
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Запрос исторических данных за указанное количество часов
            # В таблице signals используется signals_date_time (не timestamp!) и signals_id (не id!)
            queries = [
                # Вариант 1: С signals_date_time (правильное название колонки)
                """
                    SELECT signals_value, signals_date_time as ts
                    FROM signals 
                    WHERE signal_id = %s AND bed_id = %s
                      AND signals_date_time >= NOW() - INTERVAL '%s hours'
                    ORDER BY signals_date_time ASC
                """,
                # Вариант 2: Просто последние записи по signals_id (если signals_date_time NULL)
                """
                    SELECT signals_value, NOW() as ts
                    FROM signals 
                    WHERE signal_id = %s AND bed_id = %s
                    ORDER BY signals_id DESC
                    LIMIT 1000
                """
            ]
            
            results = []
            for query in queries:
                try:
                    if 'LIMIT' in query:
                        # Для варианта 3 не используем hours
                        cursor.execute(query, (signal_id, self.bed_id))
                    else:
                        cursor.execute(query, (signal_id, self.bed_id, hours))
                    results = cursor.fetchall()
                    if results:
                        break
                except Exception as query_error:
                    logger.debug(f"Запрос не сработал, пробуем следующий: {query_error}")
                    continue
            
            if not results:
                # Последняя попытка - простой запрос без фильтра по времени по signals_id
                try:
                    conn.rollback()
                    query = """
                        SELECT signals_value, NOW() as ts
                        FROM signals 
                        WHERE signal_id = %s AND bed_id = %s
                        ORDER BY signals_id DESC
                        LIMIT 1000
                    """
                    cursor.execute(query, (signal_id, self.bed_id))
                    results = cursor.fetchall()
                    conn.commit()
                except:
                    conn.rollback()
            
            cursor.close()
            
            data_points = []
            for row in results:
                value = row.get('signals_value')
                timestamp = row.get('ts')
                if value is not None:
                    # Если timestamp None, используем текущее время
                    if timestamp is None:
                        from datetime import datetime
                        timestamp = datetime.now()
                    # Преобразуем timestamp в datetime если это строка
                    elif isinstance(timestamp, str):
                        try:
                            from datetime import datetime
                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            from datetime import datetime
                            timestamp = datetime.now()
                    
                    # Убираем timezone для совместимости (приводим к offset-naive)
                    if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                        timestamp = timestamp.replace(tzinfo=None)
                    
                    data_points.append((float(value), timestamp))
            
            return data_points
                
        except Exception as e:
            logger.error(f"Ошибка получения исторических данных для signal_id={signal_id}, bed_id={self.bed_id}: {e}")
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_historical_data_between(
        self,
        signal_id: int,
        start_dt: datetime,
        end_dt: datetime,
        limit: Optional[int] = None,
    ) -> List[Tuple[float, datetime]]:
        """
        Получить исторические данные для указанного signal_id и bed_id в абсолютном диапазоне времени.

        Args:
            signal_id: ID сигнала из таблицы signal_param
            start_dt: Начало диапазона (включительно)
            end_dt: Конец диапазона (включительно)
            limit: Опциональный лимит количества точек

        Returns:
            List[Tuple[float, datetime]]: Список (value, timestamp)
        """
        if not self.connection_pool:
            logger.warning("Нет подключения к базе данных")
            return []

        if self.bed_id is None:
            logger.warning("Не выбрана кровать (bed_id = None)")
            return []

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Основной запрос по signals_date_time
            query = """
                SELECT signals_value, signals_date_time as ts
                FROM signals
                WHERE signal_id = %s
                  AND bed_id = %s
                  AND signals_date_time IS NOT NULL
                  AND signals_date_time >= %s
                  AND signals_date_time <= %s
                ORDER BY signals_date_time ASC
            """
            if limit is not None and int(limit) > 0:
                query += "\nLIMIT %s"
                params = (signal_id, self.bed_id, start_dt, end_dt, int(limit))
            else:
                params = (signal_id, self.bed_id, start_dt, end_dt)

            conn.rollback()
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.commit()
            cursor.close()

            data_points: List[Tuple[float, datetime]] = []
            for row in results:
                value = row.get("signals_value")
                ts = row.get("ts")
                if value is None or ts is None:
                    continue

                # Приводим timezone-aware -> naive для совместимости с графиками
                if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)

                try:
                    data_points.append((float(value), ts))
                except Exception:
                    continue

            return data_points
        except Exception as e:
            logger.error(
                f"Ошибка получения исторических данных (between) для signal_id={signal_id}, bed_id={self.bed_id}: {e}"
            )
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_bed_info(self, bed_id: Optional[int] = None) -> Optional[Dict]:
        """
        Получить информацию о кровати (room_id, block_id, name).
        Если bed_id не передан — используется текущий self.bed_id.
        """
        target_bed_id = bed_id if bed_id is not None else self.bed_id
        if target_bed_id is None:
            return None
        if not self.connection_pool:
            return None

        conn = None
        cursor = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                """
                SELECT bed_id, bed_name, bed_numb, room_id, block_id, status_id, patient_id
                FROM bed
                WHERE bed_id = %s
                """,
                (target_bed_id,),
            )
            row = cursor.fetchone()
            conn.commit()
            if not row:
                return None
            result = dict(row)
            result.setdefault("id", result.get("bed_id"))
            result.setdefault("name", result.get("bed_name"))
            return result
        except Exception as e:
            logger.error(f"Ошибка получения bed info для bed_id={target_bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                self.connection_pool.putconn(conn)

    def get_worklist_sessions_for_bed(
        self,
        bed_id: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict]:
        """
        Получить список "сессий" из таблицы worklist для заданной кровати
        (по совпадению room_id+block_id) и пересечению с выбранным периодом.

        Возвращает список словарей со следующими полями:
          - session_id (worklist_id)
          - begin_dt, end_dt (datetime)
          - patient_id, doctor_id, room_id, block_id
          - descr, text
        """
        if not self.connection_pool:
            return []

        bed = self.get_bed_info(bed_id)
        if not bed:
            return []

        room_id = bed.get("room_id")
        block_id = bed.get("block_id")

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Комбинируем date_beg+time_beg / date_end+time_end в timestamp
            # и выбираем записи, которые пересекаются с [start_dt, end_dt]
            conn.rollback()
            cursor.execute(
                """
                SELECT
                    worklist_id,
                    patient_id,
                    doctor_id,
                    room_id,
                    block_id,
                    date_beg,
                    date_end,
                    time_beg,
                    time_end,
                    worklist_descr,
                    worklist_text,
                    (date_beg::timestamp + COALESCE(time_beg, time '00:00')) AS begin_dt,
                    (COALESCE(date_end, date_beg)::timestamp + COALESCE(time_end, time '23:59')) AS end_dt
                FROM worklist
                WHERE room_id = %s
                  AND block_id = %s
                  AND (date_beg IS NOT NULL)
                  AND (
                        (date_beg::timestamp + COALESCE(time_beg, time '00:00')) <= %s
                    AND (COALESCE(date_end, date_beg)::timestamp + COALESCE(time_end, time '23:59')) >= %s
                  )
                ORDER BY begin_dt ASC
                """,
                (room_id, block_id, end_dt, start_dt),
            )
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            sessions: List[Dict] = []
            for r in rows or []:
                bdt = r.get("begin_dt")
                edt = r.get("end_dt")
                if bdt is None or edt is None:
                    continue
                # tz-aware -> naive
                if hasattr(bdt, "tzinfo") and bdt.tzinfo is not None:
                    bdt = bdt.replace(tzinfo=None)
                if hasattr(edt, "tzinfo") and edt.tzinfo is not None:
                    edt = edt.replace(tzinfo=None)
                sessions.append(
                    {
                        "session_id": r.get("worklist_id"),
                        "begin_dt": bdt,
                        "end_dt": edt,
                        "patient_id": r.get("patient_id"),
                        "doctor_id": r.get("doctor_id"),
                        "room_id": r.get("room_id"),
                        "block_id": r.get("block_id"),
                        "descr": r.get("worklist_descr"),
                        "text": r.get("worklist_text"),
                    }
                )
            return sessions
        except Exception as e:
            logger.error(f"Ошибка получения worklist sessions для bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_current_patient_info_for_bed(self, bed_id: int) -> Optional[Dict]:
        """Получить текущие данные пациента для кровати.

        Логика поиска:
        1) Если у кровати указан прямой `bed.patient_id > 0` — берём пациента по нему,
           а в качестве `admitted_at` подбираем последний worklist для этого пациента.
        2) Если `bed.patient_id == 0` — считаем, что пациент за этой койкой явно
           отсутствует (возвращаем None), даже если соседняя койка в той же
           (room_id, block_id) комбинации имеет активный worklist.
        3) Если `bed.patient_id IS NULL` (унаследованные данные) — используем
           старый fallback по (room_id, block_id) через worklist.
        Возвращает `None`, если пациент явно не зарегистрирован за кроватью.
        """
        if not self.connection_pool:
            return None

        bed = self.get_bed_info(bed_id)
        if not bed:
            return None
        room_id = bed.get("room_id")
        block_id = bed.get("block_id")
        bed_patient_id = bed.get("patient_id")
        bed_patient_known = bed_patient_id is not None
        try:
            bed_patient_id_int = int(bed_patient_id) if bed_patient_id is not None else 0
        except Exception:
            bed_patient_id_int = 0

        # bed.patient_id == 0 трактуем как явное "пациент отсутствует":
        # ни прямой lookup, ни worklist-fallback не выполняем.
        if bed_patient_known and bed_patient_id_int == 0:
            return None

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()

            row = None
            if bed_patient_id_int > 0:
                cursor.execute(
                    """
                    SELECT
                        w.worklist_id,
                        w.worklist_numb,
                        p.patient_id,
                        w.date_beg,
                        w.time_beg,
                        (w.date_beg::timestamp + COALESCE(w.time_beg, time '00:00')) AS admitted_at,
                        p.patient_numb,
                        p.patient_name,
                        p.patient_birth_date,
                        EXTRACT(YEAR FROM age(CURRENT_DATE, p.patient_birth_date))::int AS patient_age
                    FROM patient p
                    LEFT JOIN LATERAL (
                        SELECT w.*
                        FROM worklist w
                        WHERE w.patient_id = p.patient_id
                          AND w.date_beg IS NOT NULL
                        ORDER BY (w.date_beg::timestamp + COALESCE(w.time_beg, time '00:00')) DESC,
                                 w.worklist_id DESC
                        LIMIT 1
                    ) w ON TRUE
                    WHERE p.patient_id = %s
                    LIMIT 1
                    """,
                    (bed_patient_id_int,),
                )
                row = cursor.fetchone()

            if row is None:
                cursor.execute(
                    """
                    SELECT
                        w.worklist_id,
                        w.worklist_numb,
                        w.patient_id,
                        w.date_beg,
                        w.time_beg,
                        (w.date_beg::timestamp + COALESCE(w.time_beg, time '00:00')) AS admitted_at,
                        p.patient_numb,
                        p.patient_name,
                        p.patient_birth_date,
                        EXTRACT(YEAR FROM age(CURRENT_DATE, p.patient_birth_date))::int AS patient_age
                    FROM worklist w
                    LEFT JOIN patient p ON p.patient_id = w.patient_id
                    WHERE w.room_id = %s
                      AND w.block_id = %s
                      AND w.date_beg IS NOT NULL
                      AND (w.date_beg::timestamp + COALESCE(w.time_beg, time '00:00')) <= NOW()
                      AND (
                            w.date_end IS NULL
                         OR (w.date_end::timestamp + COALESCE(w.time_end, time '23:59')) >= NOW()
                      )
                    ORDER BY admitted_at DESC, w.worklist_id DESC
                    LIMIT 1
                    """,
                    (room_id, block_id),
                )
                row = cursor.fetchone()
            conn.commit()
            cursor.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка получения current patient info для bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_bed_by_room_block(self, room_id: int, block_id: int) -> Optional[Dict]:
        """
        Найти кровать по (room_id, block_id).
        Используется в просмотрщике истории при выборе study/worklist записи.
        """
        if not self.connection_pool:
            return None

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                """
                SELECT bed_id, bed_name, bed_numb, room_id, block_id, status_id, patient_id
                FROM bed
                WHERE room_id = %s AND block_id = %s
                ORDER BY bed_id ASC
                LIMIT 1
                """,
                (int(room_id), int(block_id)),
            )
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Ошибка поиска bed по room_id={room_id}, block_id={block_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_recent_studies(self, limit: int = 200) -> List[Dict]:
        """
        Получить список последних study из таблицы study.

        Возвращает список словарей:
          - study_id
          - study_numb
          - patient_id, doctor_id, bed_id
          - descr, text
          - begin_dt, end_dt (datetime)
        """
        if not self.connection_pool:
            return []

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                """
                SELECT
                    s.study_id,
                    s.study_numb,
                    s.patient_id,
                    p.patient_name,
                    s.doctor_id,
                    s.bed_id,
                    b.bed_name,
                    s.study_descr AS descr,
                    s.study_text AS text,
                    (s.date_beg::timestamp + COALESCE(s.time_beg, time '00:00')) AS begin_dt,
                    (COALESCE(s.date_end, s.date_beg)::timestamp + COALESCE(s.time_end, time '23:59')) AS end_dt
                FROM study s
                LEFT JOIN patient p ON p.patient_id = s.patient_id
                LEFT JOIN bed b ON b.bed_id = s.bed_id
                WHERE s.date_beg IS NOT NULL
                ORDER BY begin_dt DESC NULLS LAST, study_id DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: List[Dict] = []
            for r in rows or []:
                bdt = r.get("begin_dt")
                edt = r.get("end_dt")
                # tz-aware -> naive
                if hasattr(bdt, "tzinfo") and bdt is not None and bdt.tzinfo is not None:
                    bdt = bdt.replace(tzinfo=None)
                if hasattr(edt, "tzinfo") and edt is not None and edt.tzinfo is not None:
                    edt = edt.replace(tzinfo=None)
                out.append(
                    {
                        "study_id": r.get("study_id"),
                        "study_numb": r.get("study_numb"),
                        "patient_id": r.get("patient_id"),
                        "patient_name": r.get("patient_name"),
                        "doctor_id": r.get("doctor_id"),
                        "bed_id": r.get("bed_id"),
                        "bed_name": r.get("bed_name"),
                        "descr": r.get("descr"),
                        "text": r.get("text"),
                        "begin_dt": bdt,
                        "end_dt": edt,
                    }
                )
            return out
        except Exception as e:
            logger.error(f"Ошибка получения recent studies: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def search_studies(self, filters: Dict[str, str], limit: int = 200) -> List[Dict]:
        """Поиск study по колонковым фильтрам во всей БД с ограничением на выдачу."""
        if not self.connection_pool:
            return []

        normalized_filters = {
            str(k): str(v).strip()
            for k, v in (filters or {}).items()
            if str(v).strip()
        }
        if not normalized_filters:
            return self.get_recent_studies(limit=limit)

        where_parts = ["s.date_beg IS NOT NULL"]
        params: List[object] = []

        for key, raw in normalized_filters.items():
            if key == "study_id":
                try:
                    params.append(int(raw))
                    where_parts.append("s.study_id = %s")
                except Exception:
                    return []
            elif key == "study_numb":
                where_parts.append("COALESCE(s.study_numb::text, '') ILIKE %s")
                params.append(f"%{raw}%")
            elif key == "patient_name":
                where_parts.append("COALESCE(p.patient_name, '') ILIKE %s")
                params.append(f"%{raw}%")
            elif key == "bed_name":
                where_parts.append("COALESCE(b.bed_name, '') ILIKE %s")
                params.append(f"%{raw}%")
            elif key == "begin_dt":
                where_parts.append(
                    "to_char((s.date_beg::timestamp + COALESCE(s.time_beg, time '00:00')), 'DD.MM.YYYY HH24:MI:SS') ILIKE %s"
                )
                params.append(f"%{raw}%")
            elif key == "descr":
                where_parts.append("COALESCE(s.study_descr, '') ILIKE %s")
                params.append(f"%{raw}%")

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                f"""
                SELECT
                    s.study_id,
                    s.study_numb,
                    s.patient_id,
                    p.patient_name,
                    s.doctor_id,
                    s.bed_id,
                    b.bed_name,
                    s.study_descr AS descr,
                    s.study_text AS text,
                    (s.date_beg::timestamp + COALESCE(s.time_beg, time '00:00')) AS begin_dt,
                    (COALESCE(s.date_end, s.date_beg)::timestamp + COALESCE(s.time_end, time '23:59')) AS end_dt
                FROM study s
                LEFT JOIN patient p ON p.patient_id = s.patient_id
                LEFT JOIN bed b ON b.bed_id = s.bed_id
                WHERE {" AND ".join(where_parts)}
                ORDER BY begin_dt DESC NULLS LAST, study_id DESC
                LIMIT %s
                """,
                (*params, int(limit)),
            )
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: List[Dict] = []
            for r in rows or []:
                bdt = r.get("begin_dt")
                edt = r.get("end_dt")
                if hasattr(bdt, "tzinfo") and bdt is not None and bdt.tzinfo is not None:
                    bdt = bdt.replace(tzinfo=None)
                if hasattr(edt, "tzinfo") and edt is not None and edt.tzinfo is not None:
                    edt = edt.replace(tzinfo=None)
                out.append(
                    {
                        "study_id": r.get("study_id"),
                        "study_numb": r.get("study_numb"),
                        "patient_id": r.get("patient_id"),
                        "patient_name": r.get("patient_name"),
                        "doctor_id": r.get("doctor_id"),
                        "bed_id": r.get("bed_id"),
                        "bed_name": r.get("bed_name"),
                        "descr": r.get("descr"),
                        "text": r.get("text"),
                        "begin_dt": bdt,
                        "end_dt": edt,
                    }
                )
            return out
        except Exception as e:
            logger.error(f"Ошибка поиска studies по фильтрам {normalized_filters}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_study_by_id(self, study_id: int) -> Optional[Dict]:
        """Получить одну запись study по ID (таблица study)."""
        if not self.connection_pool:
            return None

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                """
                SELECT
                    s.study_id,
                    s.study_numb,
                    s.patient_id,
                    p.patient_name,
                    s.doctor_id,
                    s.bed_id,
                    b.bed_name,
                    s.study_descr AS descr,
                    s.study_text AS text,
                    (s.date_beg::timestamp + COALESCE(s.time_beg, time '00:00')) AS begin_dt,
                    (COALESCE(s.date_end, s.date_beg)::timestamp + COALESCE(s.time_end, time '23:59')) AS end_dt
                FROM study s
                LEFT JOIN patient p ON p.patient_id = s.patient_id
                LEFT JOIN bed b ON b.bed_id = s.bed_id
                WHERE s.study_id = %s
                """,
                (int(study_id),),
            )
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            if not row:
                return None

            bdt = row.get("begin_dt")
            edt = row.get("end_dt")
            if hasattr(bdt, "tzinfo") and bdt is not None and bdt.tzinfo is not None:
                bdt = bdt.replace(tzinfo=None)
            if hasattr(edt, "tzinfo") and edt is not None and edt.tzinfo is not None:
                edt = edt.replace(tzinfo=None)

            return {
                "study_id": row.get("study_id"),
                "study_numb": row.get("study_numb"),
                "patient_id": row.get("patient_id"),
                "patient_name": row.get("patient_name"),
                "doctor_id": row.get("doctor_id"),
                "bed_id": row.get("bed_id"),
                "bed_name": row.get("bed_name"),
                "descr": row.get("descr"),
                "text": row.get("text"),
                "begin_dt": bdt,
                "end_dt": edt,
            }
        except Exception as e:
            logger.error(f"Ошибка получения study_id={study_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_studies_for_bed_between(self, bed_id: int, start_dt: datetime, end_dt: datetime) -> List[Dict]:
        """
        Получить список study для конкретной кровати, которые пересекаются с периодом [start_dt, end_dt].

        Возвращает список словарей:
          - study_id
          - patient_id
          - begin_dt, end_dt
        """
        if not self.connection_pool:
            return []
        if bed_id is None:
            return []

        # tz-aware -> naive
        if hasattr(start_dt, "tzinfo") and start_dt.tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=None)
        if hasattr(end_dt, "tzinfo") and end_dt.tzinfo is not None:
            end_dt = end_dt.replace(tzinfo=None)

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                """
                SELECT
                    study_id,
                    patient_id,
                    (date_beg::timestamp + COALESCE(time_beg, time '00:00')) AS begin_dt,
                    (COALESCE(date_end, date_beg)::timestamp + COALESCE(time_end, time '23:59')) AS end_dt
                FROM study
                WHERE bed_id = %s
                  AND date_beg IS NOT NULL
                  AND (date_beg::timestamp + COALESCE(time_beg, time '00:00')) <= %s
                  AND (COALESCE(date_end, date_beg)::timestamp + COALESCE(time_end, time '23:59')) >= %s
                ORDER BY begin_dt ASC NULLS LAST, study_id ASC
                """,
                (int(bed_id), end_dt, start_dt),
            )
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: List[Dict] = []
            for r in rows or []:
                bdt = r.get("begin_dt")
                edt = r.get("end_dt")
                if bdt is None or edt is None:
                    continue
                if hasattr(bdt, "tzinfo") and bdt.tzinfo is not None:
                    bdt = bdt.replace(tzinfo=None)
                if hasattr(edt, "tzinfo") and edt.tzinfo is not None:
                    edt = edt.replace(tzinfo=None)
                out.append(
                    {
                        "study_id": r.get("study_id"),
                        "patient_id": r.get("patient_id"),
                        "begin_dt": bdt,
                        "end_dt": edt,
                    }
                )
            return out
        except Exception as e:
            logger.error(f"Ошибка получения studies для bed_id={bed_id} between: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_patient_name(self, patient_id: int) -> Optional[str]:
        """Получить ФИО пациента по patient_id (таблица patient.patient_name)."""
        if not self.connection_pool:
            return None
        if patient_id is None:
            return None

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            conn.rollback()
            cursor.execute(
                """
                SELECT patient_name
                FROM patient
                WHERE patient_id = %s
                """,
                (int(patient_id),),
            )
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            if not row:
                return None
            name = row.get("patient_name")
            return str(name) if name else None
        except Exception as e:
            logger.error(f"Ошибка получения patient_name для patient_id={patient_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_anesthesia_signal_params(self) -> List[Dict]:
        """
        Получить список сигналов, относящихся к анестезиологическим параметрам.

        Правило:
        - сначала пытаемся найти группы, где group_name/group_descr_rus содержит 'анест'
        - если таких нет, возвращаем все активные параметры (status_param=1 OR NULL)
        """
        if not self.connection_pool:
            return []

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            def fetch(where_sql: str, params: tuple) -> List[Dict]:
                conn.rollback()
                cursor.execute(
                    f"""
                    SELECT
                        sp.signal_id,
                        sp.signal_name,
                        sp.signal_descr_rus,
                        sp.signal_descr_eng,
                        sp.signal_unit,
                        sp.signal_min,
                        sp.signal_max,
                        sp.status_param,
                        sp.group_id,
                        g.group_name,
                        g.group_descr_rus AS group_descr_rus
                    FROM signal_param sp
                    LEFT JOIN grup g ON g.group_id = sp.group_id
                    WHERE {where_sql}
                    ORDER BY sp.group_id ASC, sp.signal_id ASC
                    """,
                    params,
                )
                rows = cursor.fetchall()
                conn.commit()
                return [dict(r) for r in (rows or [])]

            # 1) Пытаемся найти "анест*" по группе
            anest = fetch(
                "(g.group_name ILIKE %s OR g.group_descr_rus ILIKE %s) AND (sp.status_param = 1 OR sp.status_param IS NULL)",
                ("%анест%", "%анест%"),
            )
            if anest:
                cursor.close()
                return anest

            # 2) Fallback: все активные параметры
            all_active = fetch("(sp.status_param = 1 OR sp.status_param IS NULL)", ())
            cursor.close()
            return all_active
        except Exception as e:
            logger.error(f"Ошибка получения anesthesia signal params: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_signal_values_between(
        self,
        bed_id: int,
        signal_ids: List[int],
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict]:
        """
        Получить значения сигналов для кровати за период одним запросом.

        Returns: список словарей {signal_id, ts, value}
        """
        if not self.connection_pool:
            return []
        if not signal_ids:
            return []

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            placeholders = ",".join(["%s"] * len(signal_ids))
            query = f"""
                SELECT signal_id, signals_date_time as ts, signals_value
                FROM signals
                WHERE bed_id = %s
                  AND signal_id IN ({placeholders})
                  AND signals_date_time IS NOT NULL
                  AND signals_date_time >= %s
                  AND signals_date_time <= %s
                ORDER BY ts ASC
            """
            params = (bed_id, *signal_ids, start_dt, end_dt)

            conn.rollback()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: List[Dict] = []
            for r in rows or []:
                ts = r.get("ts")
                val = r.get("signals_value")
                sid = r.get("signal_id")
                if ts is None or val is None or sid is None:
                    continue
                if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                try:
                    out.append({"signal_id": int(sid), "ts": ts, "value": float(val)})
                except Exception:
                    continue
            return out
        except Exception as e:
            logger.error(f"Ошибка получения значений сигналов between для bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_latest_image_frame(self, bed_id: int) -> Optional[Dict]:
        """
        Получить последний доступный кадр из таблицы images для кровати.

        Returns:
            {"ts": datetime, "image_bytes": bytes} | None
        """
        if not self.connection_pool:
            return None

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT images_date_time AS ts, image
                FROM images
                WHERE bed_id = %s
                  AND images_date_time IS NOT NULL
                  AND image IS NOT NULL
                  AND images_date_time <= NOW()
                ORDER BY images_date_time DESC, images_id DESC
                LIMIT 1
            """
            conn.rollback()
            cursor.execute(query, (bed_id,))
            row = cursor.fetchone()
            conn.commit()
            cursor.close()

            if not row:
                return None

            ts = row.get("ts")
            image_bytes = row.get("image")
            if ts is None or image_bytes is None:
                return None
            if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            try:
                return {
                    "ts": ts,
                    "image_bytes": bytes(image_bytes),
                }
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Ошибка получения последнего кадра images для bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_image_frames_between(
        self,
        bed_id: int,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Dict]:
        """
        Получить кадры из таблицы images за период.

        Returns:
            [{"ts": datetime, "image_bytes": bytes}, ...]
        """
        if not self.connection_pool:
            return []

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            query = """
                SELECT images_date_time AS ts, image
                FROM images
                WHERE bed_id = %s
                  AND images_date_time IS NOT NULL
                  AND image IS NOT NULL
                  AND images_date_time >= %s
                  AND images_date_time <= %s
                ORDER BY images_date_time ASC, images_id ASC
            """
            conn.rollback()
            cursor.execute(query, (bed_id, start_dt, end_dt))
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: List[Dict] = []
            for row in rows or []:
                ts = row.get("ts")
                image_bytes = row.get("image")
                if ts is None or image_bytes is None:
                    continue
                if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
                    ts = ts.replace(tzinfo=None)
                try:
                    out.append({"ts": ts, "image_bytes": bytes(image_bytes)})
                except Exception:
                    continue
            return out
        except Exception as e:
            logger.error(f"Ошибка получения кадров images за период для bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_signal_ids_with_data_between(
        self,
        bed_id: int,
        signal_ids: List[int],
        start_dt: datetime,
        end_dt: datetime,
    ) -> set[int]:
        """
        Вернуть множество signal_id, у которых есть хотя бы одна точка за период.
        """
        if not self.connection_pool or not signal_ids:
            return set()

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            placeholders = ",".join(["%s"] * len(signal_ids))
            query = f"""
                SELECT DISTINCT signal_id
                FROM signals
                WHERE bed_id = %s
                  AND signal_id IN ({placeholders})
                  AND signals_date_time IS NOT NULL
                  AND signals_date_time >= %s
                  AND signals_date_time <= %s
            """
            params = (bed_id, *signal_ids, start_dt, end_dt)

            conn.rollback()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: set[int] = set()
            for r in rows or []:
                sid = r.get("signal_id")
                if sid is None:
                    continue
                try:
                    out.add(int(sid))
                except Exception:
                    pass
            return out
        except Exception as e:
            logger.error(f"Ошибка получения signal_ids with data for bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return set()
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def get_latest_values(self, bed_id: int, signal_ids: List[int]) -> Dict[int, Optional[float]]:
        """
        Получить последние значения по нескольким signal_id для одной кровати одним запросом.

        Returns:
            dict {signal_id: value_or_None}
        """
        if not self.connection_pool:
            return {}
        if not signal_ids:
            return {}

        conn = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            placeholders = ",".join(["%s"] * len(signal_ids))
            # DISTINCT ON быстро выбирает по одному последнему ряду на signal_id
            query = f"""
                SELECT DISTINCT ON (signal_id)
                    signal_id,
                    signals_value
                FROM signals
                WHERE bed_id = %s
                  AND signal_id IN ({placeholders})
                ORDER BY signal_id,
                         signals_date_time DESC NULLS LAST,
                         signals_id DESC
            """
            params = (bed_id, *signal_ids)

            conn.rollback()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.commit()
            cursor.close()

            out: Dict[int, Optional[float]] = {int(s): None for s in signal_ids}
            for r in rows or []:
                sid = r.get("signal_id")
                val = r.get("signals_value")
                if sid is None:
                    continue
                try:
                    out[int(sid)] = float(val) if val is not None else None
                except Exception:
                    out[int(sid)] = None
            return out
        except Exception as e:
            logger.error(f"Ошибка получения latest values для bed_id={bed_id}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return {}
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def close(self):
        """Освободить ресурсы экземпляра, не разрушая общий пул процесса."""
        if self._closed:
            return

        connection_pool = self.connection_pool
        pool_kind = self._pool_kind
        self.connection_pool = None
        self._pool_kind = "none"
        self._closed = True

        if connection_pool and pool_kind == "private":
            connection_pool.closeall()
        logger.info("Источник данных базы данных закрыт")

