"""
Утилиты для сохранения и загрузки конфигураций раскладок мониторов
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime


class LayoutConfig:
    """Класс для работы с конфигурациями раскладок"""
    
    CONFIG_FILE = 'layout_configs.json'
    
    @staticmethod
    def get_config_path():
        """Получить путь к файлу конфигураций"""
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_dir, LayoutConfig.CONFIG_FILE)
    
    @staticmethod
    def load_all_configs() -> List[Dict]:
        """Загрузить все конфигурации раскладок"""
        config_path = LayoutConfig.get_config_path()
        
        if not os.path.exists(config_path):
            return []
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)
                return configs if isinstance(configs, list) else []
        except Exception as e:
            print(f"Ошибка загрузки конфигураций: {e}")
            return []
    
    @staticmethod
    def save_config(config: Dict) -> bool:
        """Сохранить конфигурацию раскладки"""
        configs = LayoutConfig.load_all_configs()
        
        # Проверяем, существует ли уже конфигурация с таким ID
        config_id = config.get('id')
        if config_id:
            # Обновляем существующую
            for i, existing_config in enumerate(configs):
                if existing_config.get('id') == config_id:
                    config['updated_at'] = datetime.now().isoformat()
                    configs[i] = config
                    break
            else:
                # Если не найдена, добавляем новую
                if 'created_at' not in config:
                    config['created_at'] = datetime.now().isoformat()
                config['updated_at'] = datetime.now().isoformat()
                configs.append(config)
        else:
            # Создаем новую конфигурацию
            config['id'] = datetime.now().strftime('%Y%m%d_%H%M%S')
            config['created_at'] = datetime.now().isoformat()
            config['updated_at'] = datetime.now().isoformat()
            configs.append(config)
        
        try:
            config_path = LayoutConfig.get_config_path()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(configs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False
    
    @staticmethod
    def delete_config(config_id: str) -> bool:
        """Удалить конфигурацию раскладки"""
        configs = LayoutConfig.load_all_configs()
        
        # Удаляем конфигурацию с указанным ID
        original_count = len(configs)
        configs = [c for c in configs if c.get('id') != config_id]
        
        if len(configs) == original_count:
            return False  # Конфигурация не найдена
        
        try:
            config_path = LayoutConfig.get_config_path()
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(configs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка удаления конфигурации: {e}")
            return False
    
    @staticmethod
    def get_config(config_id: str) -> Optional[Dict]:
        """Получить конфигурацию по ID"""
        configs = LayoutConfig.load_all_configs()
        for config in configs:
            if config.get('id') == config_id:
                return config
        return None
    
    @staticmethod
    def create_default_dashboard_grid(variant: str = "two_graphs_sidebar") -> Dict:
        """Дефолтная внутренняя сетка одного монитора."""
        if variant == "four_graphs_values":
            variant = "graphs_4_values_4"
        if variant == "two_graphs_sidebar":
            variant = "graphs_2_values_4"

        graph_count = 2
        value_count = 4
        parts = str(variant or "").split("_")
        try:
            if "graphs" in parts:
                graph_count = int(parts[parts.index("graphs") + 1])
            if "values" in parts:
                value_count = int(parts[parts.index("values") + 1])
        except Exception:
            graph_count = 2
            value_count = 4
        graph_count = max(2, min(4, graph_count))
        value_count = 4 if value_count <= 4 else 6

        items = {
            "camera": {"col": 4, "row": 0, "colspan": 2, "rowspan": 3, "visible": True},
            "patient_panel": {"col": 4, "row": 3, "colspan": 2, "rowspan": 3, "visible": True},
        }
        graph_span = 12 // graph_count
        for idx in range(graph_count):
            items[f"graph{idx + 1}"] = {"col": 0, "row": idx * graph_span, "colspan": 4, "rowspan": graph_span, "visible": True}
        for idx in range(graph_count, 4):
            items[f"graph{idx + 1}"] = {"col": 0, "row": 0, "colspan": 4, "rowspan": graph_span, "visible": False}

        if value_count == 4:
            value_positions = [
                (4, 6, 1, 3),
                (5, 6, 1, 3),
                (4, 9, 1, 3),
                (5, 9, 1, 3),
            ]
        else:
            value_positions = [
                (4, 6, 1, 2),
                (5, 6, 1, 2),
                (4, 8, 1, 2),
                (5, 8, 1, 2),
                (4, 10, 1, 2),
                (5, 10, 1, 2),
            ]
        for idx, (col, row, colspan, rowspan) in enumerate(value_positions):
            items[f"value{idx + 1}"] = {"col": col, "row": row, "colspan": colspan, "rowspan": rowspan, "visible": True}
        for idx in range(value_count, 6):
            items[f"value{idx + 1}"] = {"col": 4, "row": 10, "colspan": 1, "rowspan": 2, "visible": False}

        return {
            "cols": 6,
            "rows": 12,
            "items": items,
        }

    VIEWER_DASHBOARD_GRID_FILE = "viewer_dashboard_grid.json"

    @staticmethod
    def get_viewer_dashboard_grid_path() -> str:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_dir, LayoutConfig.VIEWER_DASHBOARD_GRID_FILE)

    @staticmethod
    def load_viewer_dashboard_grid() -> Dict:
        """Загрузить сетку плиток для bed viewer (отдельно от live-раскладок)."""
        path = LayoutConfig.get_viewer_dashboard_grid_path()
        if not os.path.exists(path):
            return LayoutConfig.create_default_dashboard_grid("graphs_2_values_4")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else LayoutConfig.create_default_dashboard_grid("graphs_2_values_4")
        except Exception as e:
            print(f"Ошибка загрузки сетки просмотрщика: {e}")
            return LayoutConfig.create_default_dashboard_grid("graphs_2_values_4")

    @staticmethod
    def save_viewer_dashboard_grid(cfg: Dict) -> bool:
        """Сохранить сетку плиток bed viewer."""
        try:
            path = LayoutConfig.get_viewer_dashboard_grid_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения сетки просмотрщика: {e}")
            return False

    @staticmethod
    def create_default_config(monitor_count: int, name: str = None) -> Dict:
        """Создать конфигурацию по умолчанию"""
        if name is None:
            name = f"Раскладка {monitor_count} монитор{'ов' if monitor_count > 1 else ''}"
        
        monitors = []
        for i in range(monitor_count):
            monitors.append({
                'bed_id': None,
                'bed_name': None,
                'time_range': 'MIN_5',  # По умолчанию 5 минут
                'slots': {
                    'graph1': {'signal_id': None},
                    'graph2': {'signal_id': None},
                    'graph3': {'signal_id': None},
                    'graph4': {'signal_id': None},
                    'value1': {'signal_id': None},
                    'value2': {'signal_id': None},
                    'value3': {'signal_id': None},
                    'value4': {'signal_id': None},
                    'value5': {'signal_id': None},
                    'value6': {'signal_id': None}
                },
                'dashboard_grid': LayoutConfig.create_default_dashboard_grid(),
                'graphs': {
                    'spo2': {'signal_id': None, 'enabled': True},
                    'pulse': {'signal_id': None, 'enabled': True},
                    'breathing': {'signal_id': None, 'enabled': True},
                    'temperature': {'signal_id': None, 'enabled': True}
                },
                'display_values': {
                    'param1': None,
                    'param2': None
                }
            })
        
        return {
            'name': name,
            'monitor_count': monitor_count,
            'monitors': monitors
        }

