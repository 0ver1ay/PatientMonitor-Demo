# PatientMonitor

Настольное приложение для мониторинга витальных показателей пациентов.  
**Python · Kivy · PostgreSQL**

> Демонстрационный / портфолио-релиз. Не является медицинским изделием.  
> Не используйте реальные клинические данные пациентов.

---

## Что это

Многооконный монитор коек: показатели в реальном времени, исторические графики, настраиваемые раскладки и экспорт в CSV / XLS / PDF / XML.

Стек рассчитан на Windows и локальную или серверную PostgreSQL.

## Возможности

- **Несколько коек** — несколько окон мониторов, сетки на 2–8 панелей
- **Графики в реальном времени** — SpO₂, пульс, дыхание, температура, АД, газы и др.
- **История** — выбор исследования и временного диапазона, агрегация
- **Редактор раскладок** — пресеты и пользовательские сетки
- **Экспорт** — CSV, SpreadsheetML, PDF (ReportLab), XML для анестезии
- **Работа без БД** — при недоступной базе баннер и повтор подключения, без подмены фейковыми данными
- **Демо-режим** — синтетический генератор без PostgreSQL (по явному флагу)

## Архитектура

```
main.py / run_monitor_window.py / run_bed_viewer.py
        │
        ▼
┌───────────────────┐     ┌────────────────────┐
│  Интерфейс Kivy   │────▶│  DataSource ABC    │
│  components/      │     └─────────┬──────────┘
└───────────────────┘               │
                        ┌───────────┴───────────┐
                        ▼                       ▼
               DataGenerator              DatabaseDataSource
               (демо-режим)               (PostgreSQL + пул)
```

Ключевые модули:

| Путь | Роль |
|------|------|
| `components/` | Экраны и виджеты (монитор, графики, раскладки, экспорт) |
| `utils/database_source.py` | Запросы к БД: актуальные значения и история |
| `utils/data_generator.py` | Синтетические сигналы для демо |
| `utils/shared_db_pool.py` | Пул соединений PostgreSQL |
| `utils/signal_registry.py` | Реестр сигналов из конфига |
| `migrations/` | SQL-миграции (индексы для истории и актуальных значений) |

## Быстрый старт

### 1. Окружение

```powershell
python -m venv venv
.\activate_venv.ps1
pip install -r requirements.txt
```

### 2. Конфиг

```powershell
copy config.ini.example config.local.ini
# укажите host / port / user / password PostgreSQL
```

Переопределение через переменные окружения:

- `PATIENTMONITOR_DB_HOST`
- `PATIENTMONITOR_DB_PORT`
- `PATIENTMONITOR_DB_NAME`
- `PATIENTMONITOR_DB_USER`
- `PATIENTMONITOR_DB_PASSWORD`

### 3a. Демо без базы данных

В `config.local.ini`: `mode = demo`  
и в окружении:

```powershell
$env:PATIENTMONITOR_ALLOW_DEMO_MODE = "1"
python main.py
```

Без флага окружения `mode=demo` игнорируется — остаётся безопасный режим `database`.

### 3b. Полное демо с PostgreSQL

```powershell
python create_database.py
python import_database.py          # demo/med.sql — синтетический дамп
python apply_migrations.py
python seed_test_data.py           # опционально: плотные сигналы
python check_db_connection.py
python main.py
python run_bed_viewer.py
```

Генераторы сигналов и истории (только на демо-БД):

```powershell
python run_live_db_writer.py
python create_dense_demo_study.py
python create_live_demo_images.py
```

## Тесты

```powershell
python -m unittest discover -s tests -v
```

## Стек

- Python 3.11+
- [Kivy](https://kivy.org/) — интерфейс
- [psycopg2](https://www.psycopg.org/) — PostgreSQL
- [ReportLab](https://www.reportlab.com/) — экспорт в PDF

## Важно

- `demo/med.sql` — **синтетический** набор (`Пациент-N`), не клинические данные
- `config.ini` / `config.local.ini` не коммитятся — в репозитории только `config.ini.example`
- Не запускайте seed / live-writer против не-демо базы
- Вендорный bedside-стек и production-конфиги в этот репозиторий **не входят**

## Лицензия

MIT — см. [LICENSE](LICENSE)
