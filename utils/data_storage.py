"""
Хранение и загрузка истории данных монитора пациента
"""
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class DataStorage:
    """Класс для сохранения и загрузки данных монитора"""
    
    def __init__(self, data_file: str = "patient_data.json"):
        """
        Инициализация хранилища данных
        
        Args:
            data_file: Путь к файлу с данными
        """
        self.data_file = Path(data_file)
        self.data_dir = self.data_file.parent
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def save_data_point(self, parameter: str, value: float, timestamp: datetime = None):
        """
        Сохранение одной точки данных
        
        Args:
            parameter: Название параметра (spo2, pulse, breathing, temperature)
            value: Значение (float)
            timestamp: Время измерения (если None, используется текущее время)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Загружаем существующие данные
        data = self.load_all_data()
        
        # Добавляем новую точку
        if parameter not in data:
            data[parameter] = []
        
        data[parameter].append({
            'value': float(value),
            'timestamp': timestamp.isoformat()
        })
        
        # Удаляем старые данные (старше 24 часов)
        cutoff_time = datetime.now() - timedelta(hours=24)
        data[parameter] = [
            point for point in data[parameter]
            if datetime.fromisoformat(point['timestamp']) >= cutoff_time
        ]
        
        # Сохраняем обратно
        self._save_data(data)
    
    def load_data(self, parameter: str, hours: int = 6) -> List[Tuple[float, datetime]]:
        """
        Загрузка данных параметра за указанный период
        
        Args:
            parameter: Название параметра
            hours: Количество часов истории (по умолчанию 6)
            
        Returns:
            Список кортежей (value, timestamp)
        """
        all_data = self.load_all_data()
        
        if parameter not in all_data:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        result = []
        for point in all_data[parameter]:
            timestamp = datetime.fromisoformat(point['timestamp'])
            if timestamp >= cutoff_time:
                result.append((point['value'], timestamp))
        
        # Сортируем по времени
        result.sort(key=lambda x: x[1])
        return result

    def load_data_between(
        self,
        parameter: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> List[Tuple[float, datetime]]:
        """
        Загрузка данных параметра в абсолютном диапазоне времени.

        Args:
            parameter: Название параметра
            start_dt: Начало диапазона (включительно)
            end_dt: Конец диапазона (включительно)

        Returns:
            Список кортежей (value, timestamp)
        """
        all_data = self.load_all_data()

        if parameter not in all_data:
            return []

        result: List[Tuple[float, datetime]] = []
        for point in all_data[parameter]:
            try:
                timestamp = datetime.fromisoformat(point["timestamp"])
            except Exception:
                continue
            if start_dt <= timestamp <= end_dt:
                result.append((point["value"], timestamp))

        result.sort(key=lambda x: x[1])
        return result
    
    def load_all_data(self) -> Dict[str, List[Dict]]:
        """
        Загрузка всех данных из файла
        
        Returns:
            Словарь с данными всех параметров
        """
        if not self.data_file.exists():
            return {
                'spo2': [],
                'pulse': [],
                'breathing': [],
                'temperature': []
            }
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError):
            return {
                'spo2': [],
                'pulse': [],
                'breathing': [],
                'temperature': []
            }
    
    def _save_data(self, data: Dict[str, List[Dict]]):
        """Сохранение данных в файл"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Ошибка сохранения данных: {e}")
    
    def generate_test_data(self, hours: int = 6):
        """
        Генерация тестовых данных за указанный период (для демонстрации)
        
        Args:
            hours: Количество часов истории
        """
        import random
        import math
        
        now = datetime.now()
        start_time = now - timedelta(hours=hours)
        
        # Генерируем данные каждую секунду
        current_time = start_time
        data = {
            'spo2': [],
            'pulse': [],
            'breathing': [],
            'temperature': []
        }
        
        time_offset = 0
        while current_time < now:
            # SPO2
            spo2_value = 98.0 + math.sin(time_offset * 0.1) * 1.5 + random.uniform(-0.5, 0.5)
            spo2_value = max(95.0, min(100.0, spo2_value))
            
            # Pulse
            pulse_value = 72.0 + math.sin(time_offset * 0.2) * 8 + random.uniform(-3, 3)
            pulse_value = max(60.0, min(100.0, pulse_value))
            
            # Breathing
            breathing_value = 16.0 + math.sin(time_offset * 0.05) * 2 + random.uniform(-1, 1)
            breathing_value = max(12.0, min(20.0, breathing_value))
            
            # Temperature
            temp_value = 36.6 + math.sin(time_offset * 0.01) * 0.3 + random.uniform(-0.1, 0.1)
            temp_value = max(36.0, min(37.5, temp_value))
            
            data['spo2'].append({'value': spo2_value, 'timestamp': current_time.isoformat()})
            data['pulse'].append({'value': pulse_value, 'timestamp': current_time.isoformat()})
            data['breathing'].append({'value': breathing_value, 'timestamp': current_time.isoformat()})
            data['temperature'].append({'value': temp_value, 'timestamp': current_time.isoformat()})
            
            current_time += timedelta(seconds=1)
            time_offset += 1
        
        self._save_data(data)













