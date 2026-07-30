"""
Утилиты для управления временными диапазонами
"""
from enum import Enum


class TimeRange(Enum):
    """Доступные временные диапазоны"""
    MIN_1 = (1, "1 минута")
    MIN_2 = (2, "2 минуты")
    MIN_5 = (5, "5 минут")
    MIN_10 = (10, "10 минут")
    MIN_30 = (30, "30 минут")
    MIN_60 = (60, "60 минут")
    HOUR_2 = (120, "2 часа")
    HOUR_4 = (240, "4 часа")
    HOUR_6 = (360, "6 часов")
    HOUR_12 = (720, "12 часов")
    HOUR_24 = (1440, "24 часа")
    
    def __init__(self, minutes, label):
        self.minutes = minutes
        self.label = label
    
    @property
    def seconds(self):
        """Возвращает диапазон в секундах"""
        return self.minutes * 60
    
    @staticmethod
    def get_all_ranges():
        """Возвращает все доступные диапазоны"""
        return list(TimeRange)
    
    @staticmethod
    def get_default():
        """Возвращает диапазон по умолчанию"""
        return TimeRange.MIN_5

