"""
Скрипт для проверки подключения к базе данных PostgreSQL
Используется для диагностики проблем с подключением
"""
import sys
import socket
import psycopg2
from utils.config_loader import ConfigLoader

def check_port(host: str, port: int) -> bool:
    """Проверка доступности порта"""
    print(f"\n{'='*60}")
    print("ШАГ 1: Проверка доступности порта")
    print(f"{'='*60}")
    print(f"Хост: {host}")
    print(f"Порт: {port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"[OK] Порт {port} доступен и принимает подключения")
            return True
        else:
            print(f"[ERROR] Порт {port} недоступен (код ошибки: {result})")
            print(f"\n  Возможные причины:")
            print(f"  - PostgreSQL не запущен")
            print(f"  - PostgreSQL слушает на другом порту")
            print(f"  - Файрвол блокирует подключение")
            return False
    except socket.gaierror as e:
        print(f"[ERROR] Ошибка разрешения имени хоста '{host}': {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка проверки порта: {e}")
        return False

def check_connection(config: ConfigLoader):
    """Проверка подключения к базе данных"""
    print(f"\n{'='*60}")
    print("ШАГ 2: Попытка подключения к PostgreSQL")
    print(f"{'='*60}")
    
    host = config.get_db_host()
    port = config.get_db_port()
    database = config.get_db_name()
    user = config.get_db_user()
    password = config.get_db_password()
    
    print(f"Хост: {host}")
    print(f"Порт: {port}")
    print(f"База данных: {database}")
    print(f"Пользователь: {user}")
    print(f"Пароль: {'*' * len(password) if password else '(пустой)'}")
    
    try:
        print(f"\nПодключение...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=10
        )
        
        print(f"[OK] Подключение успешно установлено!")
        
        # Проверяем версию PostgreSQL
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\nИнформация о сервере:")
        print(f"  Версия: {version.split(',')[0]}")
        
        # Проверяем существование таблиц
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        print(f"\nДоступные таблицы ({len(tables)}):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Проверяем наличие нужных таблиц
        required_tables = ['bed', 'signals', 'signal_param']
        existing_tables = [t[0] for t in tables]
        missing_tables = [t for t in required_tables if t not in existing_tables]
        
        if missing_tables:
            print(f"\n[WARN] Отсутствуют необходимые таблицы:")
            for table in missing_tables:
                print(f"  - {table}")
        else:
            print(f"\n[OK] Все необходимые таблицы присутствуют")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] ОШИБКА ПОДКЛЮЧЕНИЯ")
        print(f"  Тип: OperationalError")
        print(f"  Сообщение: {e}")
        print(f"\n  Возможные причины:")
        print(f"  1. PostgreSQL не запущен на {host}:{port}")
        print(f"  2. Неправильный порт (стандартный порт PostgreSQL: 5432)")
        print(f"  3. База данных '{database}' не существует")
        print(f"  4. Неправильные учетные данные")
        print(f"  5. Файрвол блокирует подключение")
        print(f"  6. PostgreSQL не настроен для приема подключений")
        return False
        
    except psycopg2.Error as e:
        print(f"\n[ERROR] ОШИБКА БАЗЫ ДАННЫХ")
        print(f"  Тип: {type(e).__name__}")
        print(f"  Сообщение: {e}")
        return False
        
    except Exception as e:
        print(f"\n[ERROR] НЕИЗВЕСТНАЯ ОШИБКА")
        print(f"  Тип: {type(e).__name__}")
        print(f"  Сообщение: {e}")
        return False

def main():
    """Главная функция"""
    print("="*60)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ POSTGRESQL")
    print("="*60)
    
    # Загружаем конфигурацию
    config = ConfigLoader()
    
    host = config.get_db_host()
    port = config.get_db_port()
    
    # Проверяем порт
    port_available = check_port(host, port)
    
    if not port_available:
        print(f"\n[WARN] Рекомендация: Проверьте, запущен ли PostgreSQL")
        print(f"  Команда для проверки: pg_isready -h {host} -p {port}")
        print(f"  Или попробуйте стандартный порт: 5432")
    
    # Пытаемся подключиться
    connection_ok = check_connection(config)
    
    print(f"\n{'='*60}")
    if connection_ok:
        print("[OK] ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО")
        print("  База данных готова к использованию")
    else:
        print("[ERROR] ОБНАРУЖЕНЫ ПРОБЛЕМЫ")
        print("  Исправьте ошибки перед использованием приложения")
    print(f"{'='*60}\n")
    
    return 0 if connection_ok else 1

if __name__ == '__main__':
    sys.exit(main())









