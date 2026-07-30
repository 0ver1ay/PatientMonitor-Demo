"""
Генератор тестовых данных для монитора пациента
"""
import random
import math
from datetime import datetime, timedelta
from utils.data_source import DataSource


class DataGenerator(DataSource):
    """Генератор данных для различных параметров монитора (тестовый источник)"""
    
    def __init__(self):
        self.time = 0
        self.spo2_base = 98.0
        self.pulse_base = 72.0
        self.breathing_base = 16.0
        self.temperature_base = 36.6
    
    def get_spo2(self) -> float:
        """Получить значение SPO2 (95-100%) в формате float"""
        # Синусоида с небольшими случайными колебаниями
        variation = math.sin(self.time * 0.1) * 1.5 + random.uniform(-0.5, 0.5)
        value = self.spo2_base + variation
        return float(max(95.0, min(100.0, value)))
    
    def get_pulse(self) -> float:
        """Получить значение пульса (60-100 уд/мин) в формате float"""
        # Более выраженная синусоида для пульса
        variation = math.sin(self.time * 0.2) * 8 + random.uniform(-3, 3)
        value = self.pulse_base + variation
        return float(max(60.0, min(100.0, value)))
    
    def get_breathing(self) -> float:
        """Получить значение дыхания (12-20 вдохов/мин) в формате float"""
        # Медленная синусоида для дыхания
        variation = math.sin(self.time * 0.05) * 2 + random.uniform(-1, 1)
        value = self.breathing_base + variation
        return float(max(12.0, min(20.0, value)))
    
    def get_temperature(self) -> float:
        """Получить значение температуры (36.0-37.5°C) в формате float"""
        # Очень медленные изменения температуры
        variation = math.sin(self.time * 0.01) * 0.3 + random.uniform(-0.1, 0.1)
        value = self.temperature_base + variation
        return float(max(36.0, min(37.5, value)))
    
    def update(self, dt):
        """Обновление времени для генерации данных"""
        self.time += dt
    
    def reset(self):
        """Сброс генератора"""
        self.time = 0
    
    # Старые методы для обратной совместимости (можно удалить позже)
    def generate_spo2(self) -> float:
        """Генерация значения SPO2 (устаревший метод, используйте get_spo2)"""
        return self.get_spo2()
    
    def generate_pulse(self) -> float:
        """Генерация значения пульса (устаревший метод, используйте get_pulse)"""
        return self.get_pulse()
    
    def generate_breathing(self) -> float:
        """Генерация значения дыхания (устаревший метод, используйте get_breathing)"""
        return self.get_breathing()
    
    def generate_temperature(self) -> float:
        """Генерация значения температуры (устаревший метод, используйте get_temperature)"""
        return self.get_temperature()

