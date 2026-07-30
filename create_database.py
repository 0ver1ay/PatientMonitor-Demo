"""
Скрипт для создания базы данных PostgreSQL (если не существует)
"""
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from utils.config_loader import ConfigLoader

def create_database_if_not_exists(config: ConfigLoader):
    """
    Создает базу данных, если она не существует
    
    Args:
        config: Объект ConfigLoader с настройками подключения
    """
    print("="*60)
    print("СОЗДАНИЕ БАЗЫ ДАННЫХ POSTGRESQL")
    print("="*60)
    
    host = config.get_db_host()
    port = config.get_db_port()
    database = config.get_db_name()
    user = config.get_db_user()
    password = config.get_db_password()
    
    print(f"\nПараметры подключения:")
    print(f"  Хост: {host}")
    print(f"  Порт: {port}")
    print(f"  База данных: {database}")
    print(f"  Пользователь: {user}")
    
    try:
        # Подключаемся к базе данных postgres (системная база)
        print(f"\nПодключение к серверу PostgreSQL...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database='postgres',  # Подключаемся к системной базе
            user=user,
            password=password,
            connect_timeout=10
        )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print(f"✓ Подключение установлено")
        
        # Проверяем, существует ли база данных
        print(f"\nПроверка существования базы данных '{database}'...")
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (database,)
        )
        
        exists = cursor.fetchone()
        
        if exists:
            print(f"✓ База данных '{database}' уже существует")
            cursor.close()
            conn.close()
            return True
        else:
            print(f"✗ База данных '{database}' не найдена")
            print(f"\nСоздание базы данных '{database}'...")
            
            # Создаем базу данных
            cursor.execute(f'CREATE DATABASE "{database}"')
            
            print(f"✓ База данных '{database}' успешно создана!")
            cursor.close()
            conn.close()
            return True
            
    except psycopg2.OperationalError as e:
        print(f"\n✗ ОШИБКА ПОДКЛЮЧЕНИЯ")
        print(f"  {e}")
        print(f"\nВозможные причины:")
        print(f"  1. PostgreSQL не запущен")
        print(f"  2. Неправильные параметры подключения")
        print(f"  3. Пользователь не имеет прав на создание баз данных")
        return False
        
    except Exception as e:
        print(f"\n✗ ОШИБКА")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Главная функция"""
    config = ConfigLoader()
    
    success = create_database_if_not_exists(config)
    
    if success:
        print(f"\n{'='*60}")
        print("✓ ГОТОВО К ИМПОРТУ ДАННЫХ")
        print(f"{'='*60}")
        print(f"\nСледующий шаг: запустите импорт")
        print(f"  python import_database.py")
        print(f"  или")
        print(f"  import_database.bat")
        return 0
    else:
        print(f"\n{'='*60}")
        print("✗ НЕ УДАЛОСЬ СОЗДАТЬ БАЗУ ДАННЫХ")
        print(f"{'='*60}")
        return 1

if __name__ == '__main__':
    sys.exit(main())









