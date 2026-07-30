"""
Скрипт для импорта SQL дампа базы данных PostgreSQL
"""
import sys
import subprocess
import os
from pathlib import Path
from utils.config_loader import ConfigLoader

def find_psql():
    """Поиск psql в стандартных местах установки PostgreSQL"""
    import platform
    
    if platform.system() != 'Windows':
        return 'psql'  # На Linux/Mac обычно в PATH
    
    print("\nПоиск psql...")
    
    # Проверяем, есть ли psql в PATH
    try:
        result = subprocess.run(['psql', '--version'], 
                               capture_output=True, 
                               timeout=2,
                               shell=True)
        if result.returncode == 0:
            print("✓ Найден psql в PATH")
            return 'psql'
    except:
        pass
    
    # Стандартные пути для Windows (расширенный список версий)
    common_paths = []
    
    # Добавляем пути из переменных окружения (динамический поиск)
    if 'PROGRAMFILES' in os.environ:
        pg_dir = Path(os.environ['PROGRAMFILES']) / 'PostgreSQL'
        if pg_dir.exists():
            for version_dir in sorted(pg_dir.iterdir(), reverse=True):  # Сначала новые версии
                if version_dir.is_dir():
                    psql_path = version_dir / 'bin' / 'psql.exe'
                    if psql_path.exists():
                        common_paths.append(str(psql_path))
    
    if 'PROGRAMFILES(X86)' in os.environ:
        pg_dir = Path(os.environ['PROGRAMFILES(X86)']) / 'PostgreSQL'
        if pg_dir.exists():
            for version_dir in sorted(pg_dir.iterdir(), reverse=True):  # Сначала новые версии
                if version_dir.is_dir():
                    psql_path = version_dir / 'bin' / 'psql.exe'
                    if psql_path.exists():
                        psql_str = str(psql_path)
                        if psql_str not in common_paths:
                            common_paths.append(psql_str)
    
    # Стандартные пути (если переменные окружения не помогли)
    standard_paths = [
        r"C:\Program Files\PostgreSQL\17\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\14\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\13\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\12\bin\psql.exe",
        r"C:\Program Files (x86)\PostgreSQL\17\bin\psql.exe",
        r"C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe",
        r"C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe",
        r"C:\Program Files (x86)\PostgreSQL\14\bin\psql.exe",
        r"C:\Program Files (x86)\PostgreSQL\13\bin\psql.exe",
        r"C:\Program Files (x86)\PostgreSQL\12\bin\psql.exe",
    ]
    
    # Добавляем стандартные пути
    for path in standard_paths:
        if Path(path).exists() and path not in common_paths:
            common_paths.append(path)
    
    # Ищем в найденных путях
    for path in common_paths:
        if Path(path).exists():
            print(f"✓ Найден psql: {path}")
            return path
    
    # Если ничего не найдено, выводим информацию
    print("✗ psql не найден в стандартных местах")
    print("\nПроверенные пути:")
    for path in standard_paths[:6]:  # Показываем первые 6
        print(f"  - {path}")
    print("  ... и другие стандартные пути")
    
    return None

def import_sql_dump(sql_file: str, config: ConfigLoader):
    """
    Импорт SQL дампа в базу данных PostgreSQL
    
    Args:
        sql_file: Путь к SQL файлу
        config: Объект ConfigLoader с настройками подключения
    """
    print("="*60)
    print("ИМПОРТ БАЗЫ ДАННЫХ POSTGRESQL")
    print("="*60)
    
    sql_path = Path(sql_file)
    
    if not sql_path.exists():
        print(f"✗ Файл не найден: {sql_file}")
        return False
    
    print(f"\nФайл дампа: {sql_path}")
    print(f"Размер файла: {sql_path.stat().st_size / 1024 / 1024:.2f} MB")
    
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
    
    # Способ 1: Использование psql через переменную окружения PGPASSWORD
    print(f"\n{'='*60}")
    print("СПОСОБ 1: Использование psql (рекомендуется)")
    print(f"{'='*60}")
    
    # Ищем psql
    psql_path = find_psql()
    
    if not psql_path:
        print("\n" + "="*60)
        print("✗ КОМАНДА 'psql' НЕ НАЙДЕНА")
        print("="*60)
        print("\nВозможные решения:")
        print("\n1. Добавьте PostgreSQL в PATH:")
        print("   - Найдите каталог установки PostgreSQL")
        print("   - Обычно: C:\\Program Files\\PostgreSQL\\XX\\bin")
        print("   - Добавьте этот путь в переменную PATH")
        print("\n2. Импортируйте вручную через командную строку:")
        print("   set PGPASSWORD=<your_password>")
        print(f'   "C:\\Program Files\\PostgreSQL\\XX\\bin\\psql.exe" -h {host} -p {port} -U {user} -d {database} -f "{sql_path.absolute()}"')
        print("\n3. Используйте pgAdmin:")
        print("   - Откройте pgAdmin")
        print("   - Подключитесь к серверу")
        print("   - Правой кнопкой на базе данных -> Query Tool")
        print("   - Откройте SQL файл и выполните")
        print("\n⚠ ВАЖНО: SQL дампы с командами COPY FROM stdin")
        print("  можно импортировать ТОЛЬКО через psql!")
        print("  Python способ не поддерживает такие команды.")
        return False
    
    try:
        # Устанавливаем переменную окружения для пароля
        env = os.environ.copy()
        env['PGPASSWORD'] = password
        
        # Формируем команду psql
        psql_cmd = [
            psql_path,
            '-h', host,
            '-p', str(port),
            '-U', user,
            '-d', database,
            '-f', str(sql_path.absolute())
        ]
        
        print(f"\nНайден psql: {psql_path}")
        print(f"\nВыполняется команда:")
        print(f"  {' '.join(psql_cmd)}")
        print(f"\nИмпорт данных...")
        print(f"(Это может занять некоторое время в зависимости от размера дампа)")
        print(f"{'='*60}\n")
        
        # Выполняем команду
        result = subprocess.run(
            psql_cmd,
            env=env,
            capture_output=False,  # Показываем вывод в реальном времени
            text=True
        )
        
        if result.returncode == 0:
            print(f"\n{'='*60}")
            print("✓ ИМПОРТ УСПЕШНО ЗАВЕРШЕН!")
            print(f"{'='*60}\n")
            return True
        else:
            print(f"\n{'='*60}")
            print("✗ ОШИБКА ПРИ ИМПОРТЕ")
            print(f"  Код возврата: {result.returncode}")
            print(f"{'='*60}\n")
            return False
            
    except Exception as e:
        print(f"✗ Ошибка при выполнении psql: {e}")
        print("\n⚠ ВАЖНО: SQL дампы с командами COPY FROM stdin")
        print("  можно импортировать ТОЛЬКО через psql!")
        print("\nПопробуйте:")
        print("  1. Запустить import_database.bat")
        print("  2. Или импортировать вручную через pgAdmin")
        return False

def import_sql_dump_python(sql_file: str, config: ConfigLoader):
    """
    Альтернативный способ импорта через Python (psycopg2)
    ВНИМАНИЕ: Этот способ НЕ поддерживает команды COPY FROM stdin!
    """
    print(f"\n{'='*60}")
    print("⚠ ВАЖНО: Python способ НЕ поддерживает команды COPY FROM stdin")
    print("  SQL дампы с такими командами нужно импортировать через psql!")
    print(f"{'='*60}")
    print("\nРекомендуется использовать:")
    print("  1. import_database.bat (Windows)")
    print("  2. psql напрямую из командной строки")
    print("  3. pgAdmin")
    return False

def create_database_if_needed(config: ConfigLoader):
    """Создает базу данных, если она не существует"""
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        print("\nПроверка существования базы данных...")
        conn = psycopg2.connect(
            host=config.get_db_host(),
            port=config.get_db_port(),
            database='postgres',
            user=config.get_db_user(),
            password=config.get_db_password(),
            connect_timeout=10
        )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (config.get_db_name(),)
        )
        
        if not cursor.fetchone():
            print(f"База данных '{config.get_db_name()}' не найдена, создаем...")
            cursor.execute(f'CREATE DATABASE "{config.get_db_name()}"')
            print(f"✓ База данных создана")
        else:
            print(f"✓ База данных '{config.get_db_name()}' существует")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠ Не удалось проверить/создать базу данных: {e}")
        print("  Продолжаем импорт...")
        return False

def main():
    """Главная функция"""
    # Путь к SQL файлу
    sql_file = "demo/med.sql"
    
    # Загружаем конфигурацию
    config = ConfigLoader()
    
    # Создаем базу данных, если нужно
    create_database_if_needed(config)
    
    print(f"\n⚠ ВНИМАНИЕ:")
    print(f"  Импорт дампа может перезаписать существующие данные в базе '{config.get_db_name()}'")
    print(f"  Убедитесь, что вы хотите продолжить!")
    
    response = input("\nПродолжить импорт? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y', 'да', 'д']:
        print("\nИмпорт отменен.")
        return 1
    
    # Импортируем дамп
    success = import_sql_dump(sql_file, config)
    
    if success:
        print("\n✓ База данных успешно импортирована!")
        print("\nСледующие шаги:")
        print("1. Проверьте подключение: python check_db_connection.py")
        print("2. Запустите приложение: python main.py")
        return 0
    else:
        print("\n✗ Ошибка при импорте базы данных")
        print("\nРекомендации:")
        print("1. Убедитесь, что PostgreSQL запущен")
        print("2. Проверьте параметры подключения в config.ini")
        print("3. Убедитесь, что база данных 'med' существует")
        print("4. Попробуйте импортировать вручную через pgAdmin или psql")
        return 1

if __name__ == '__main__':
    sys.exit(main())

