# Итоговый проект по модулю Python. Курс Инженер данных.

ETL-проект: забирает статистику попыток (LTI) из API IT-resume, парсит её и загружает
в таблицу `it_resume.grader_usage` в PostgreSQL.

## Как это работает

1. `etl.py` для каждой даты диапазона делает запрос к API IT-resume.
2. Ответ парсится в набор полей: `user_id`, `oauth_consumer_key`, `lis_result_sourcedid`,
   `lis_outcome_service_url`, `is_correct`, `attempt_type`, `created_at`.
3. Строки пакетно вставляются в таблицу `it_resume.grader_usage` (`execute_values`),
   дубли игнорируются благодаря `ON CONFLICT (user_id, created_at) DO NOTHING`.
4. Каждая дата пишется в отдельный лог-файл; после загрузки старые логи
   (кроме последних 3 дней) удаляются.

## Требования

- Python 3.13
- PostgreSQL (локально или в Docker)
- Доступ к API IT-resume: `client` и `client_key`

## Быстрый старт

### 1. Виртуальное окружение и зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
```

Заполни `.env` своими значениями (описание переменных — ниже).

### 3. Подготовка базы данных

Нужна база PostgreSQL (по умолчанию из `.env.example` — `study`).
Пример запуска локальной БД в Docker:

```bash
docker run -d \
  --name it_resume_pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=study \
  -p 5432:5432 \
  postgres:16
```

Затем создай схему и таблицу:

```sql
create schema if not exists it_resume;

create table if not exists it_resume.grader_usage
(
    user_id                 varchar   not null,
    oauth_consumer_key      varchar,
    lis_result_sourcedid    varchar,
    lis_outcome_service_url varchar,
    is_correct              integer,
    attempt_type            varchar(10),
    created_at              timestamp not null,
    primary key (user_id, created_at)
);
```

### 4. Запуск

```bash
python etl.py
```

## Переменные окружения (`.env`)

| Переменная | Назначение |
| --- | --- |
| `IT_RESUME_API_URL` | URL API IT-resume, например `https://api.itresume.ru/statistics/` |
| `IT_RESUME_CLIENT` | Идентификатор клиента для доступа к API |
| `IT_RESUME_CLIENT_KEY` | Ключ клиента для доступа к API |
| `DB_HOST` | Хост PostgreSQL (`localhost`, если БД на той же машине) |
| `DB_PORT` | Порт PostgreSQL (по умолчанию `5432`) |
| `DB_USER` | Пользователь PostgreSQL |
| `DB_PASSWORD` | Пароль пользователя PostgreSQL |
| `DB_NAME` | Имя базы данных (например, `study`) |
| `APP_LOG_DIR` | Папка для лог-файлов (по умолчанию `./logs`) |

## Структура проекта

| Файл | Назначение |
| --- | --- |
| `etl.py` | Оркестрация: запрос к API, парсинг, загрузка в БД, очистка логов |
| `classes.py` | `DatabaseConnection` (Singleton-подключение) и `DatabaseOperations` (`insert_rows`, `check_last_date`, `close_connection`) |
| `utils.py` | `make_logger_for_date` (логгер на дату) и `cleanup_logs` (очистка старых логов) |
| `logs/` | Лог-файлы, создаются автоматически |
| `.env` | Локальные переменные окружения (не коммитится) |
| `.env.example` | Шаблон `.env` |

## Логи

- Формат имени файла — `<дата>.log` (например, `logs/2026-05-31.log`): **один файл = один день**.
- Хранятся в папке из `APP_LOG_DIR` (по умолчанию `./logs`).
- После загрузки `cleanup_logs` удаляет все лог-файлы, кроме последних 3 дней.

## Примечания

- **Идемпотентность.** Вставка идёт с `ON CONFLICT (user_id, created_at) DO NOTHING`,
  поэтому повторный запуск не создаёт дублей — можно запускать `python etl.py` многократно.
- **Диапазон загрузки** задаётся в `etl.py`: старт — последняя загруженная дата из БД
  (`max(date(created_at))`), окончание захардкожено (`END_DT = 2026-06-01`). При пустой БД
  загрузка начинается с `2026-05-23`.
