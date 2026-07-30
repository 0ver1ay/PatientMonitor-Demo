"""
Интерфейс источника данных для монитора пациента
Позволяет легко заменить тестовый генератор на данные из базы данных
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Set


class DataSource(ABC):
    """Абстрактный класс источника данных"""
    
    def get_value(self, signal_id: int) -> Optional[float]:
        """
        Универсальный метод получения значения параметра по signal_id
        
        Args:
            signal_id: ID сигнала из таблицы signal_param
            
        Returns:
            Optional[float]: Значение параметра или None
        """
        # Для обратной совместимости используем старые методы
        # Это будет переопределено в DatabaseDataSource
        return None
    
    def get_available_signals(self) -> List[Dict]:
        """
        Получить список доступных сигналов/параметров
        
        Returns:
            List[Dict]: Список словарей с информацией о сигналах
                       [{'signal_id': 1, 'name': 'SPO2', 'unit': '%', 'min': 90, 'max': 100}, ...]
        """
        # По умолчанию возвращаем пустой список
        # Будет переопределено в DatabaseDataSource
        return []

    def get_historical_data_between(
        self,
        signal_id: int,
        start_dt: datetime,
        end_dt: datetime,
        limit: Optional[int] = None,
    ) -> List[Tuple[float, datetime]]:
        """
        Получить исторические данные (value, timestamp) в абсолютном диапазоне времени.

        По умолчанию возвращает пустой список; переопределяется в DatabaseDataSource.
        """
        return []

    def get_signal_ids_with_data_between(
        self,
        bed_id: int,
        signal_ids: List[int],
        start_dt: datetime,
        end_dt: datetime,
    ) -> Set[int]:
        """
        Вернуть множество signal_id, у которых есть хотя бы одна точка в периоде.

        По умолчанию возвращает пустое множество; переопределяется в DatabaseDataSource.
        """
        return set()
    
    # Старые методы для обратной совместимости
    @abstractmethod
    def get_spo2(self) -> float:
        """Получить значение SPO2 (float)"""
        pass
    
    @abstractmethod
    def get_pulse(self) -> float:
        """Получить значение пульса (float)"""
        pass
    
    @abstractmethod
    def get_breathing(self) -> float:
        """Получить значение дыхания (float)"""
        pass
    
    @abstractmethod
    def get_temperature(self) -> float:
        """Получить значение температуры (float)"""
        pass
    
    def is_available(self) -> bool:
        """Проверка доступности источника данных"""
        return True

