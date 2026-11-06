import requests
import os
import sys
from datetime import datetime, timedelta, time
from classes import DatabaseConnection, DatabaseOperations
from dotenv import load_dotenv
from pathlib import Path
from utils import make_logger_for_date, cleanup_logs, parse_attempt


KEEP_LOG_DAYS = 3  #сколько дней храним логи


def main():
    #Загружаем переменные окружения
    load_dotenv()

    IT_RESUME_API_URL = os.environ.get('IT_RESUME_API_URL')

    #Настраиваем логирование
    LOG_DIR = Path(os.environ.get('APP_LOG_DIR', './logs'))
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    conn = DatabaseConnection.get_instance().get_connection()
    db_operations = DatabaseOperations(conn)

    failed_dates = []

    try:
        current_last_date = db_operations.check_last_date()
        print(current_last_date)

        #Генерируем список дат для демонстрации загрузки (когда будет airflow – заменим на логическую дату)

        START_DT = datetime.combine(current_last_date, time.min) if current_last_date else datetime(2026,5,23,0,0,0,0,None) #для демонстрации при пустой БД берем 10 дней мая для загрузки
        END_DT = datetime(2026,6,1,0,0,0,0,None) #ограничения API, данные доступны только до июня 2026 года

        days = (END_DT - START_DT).days
        dates = [START_DT + timedelta(days=i) for i in range(days)]

        for dt in dates:

            logger = make_logger_for_date(dt, 'etl_logger', LOG_DIR)

            try:
                API_PARAMS = {
                    'client': os.environ.get('IT_RESUME_CLIENT'),
                    'client_key' : os.environ.get('IT_RESUME_CLIENT_KEY'),
                    'start': dt.strftime("%Y-%m-%d %H:%M:%S.%f"),
                    'end': (dt + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S.%f")
                }

                try:
                    logger.info(f'Выгрузка за {dt.strftime('%Y-%m-%d')} запущена')
                    response = requests.get(IT_RESUME_API_URL, params=API_PARAMS, timeout=1500)
                    response.raise_for_status()
                except requests.exceptions.HTTPError as err:
                    logger.error(f"HTTP Error: {err}")
                    raise
                except requests.exceptions.RequestException as err:
                    logger.error(f"Request Error: {err}")
                    raise

                logger.info(f'Данные получены, запускается парсинг')

                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError(f'Ответ API имеет неожиданный формат: {type(payload).__name__}')

                rows = []
                skipped = 0
                for item in payload:
                    row = parse_attempt(item, logger)
                    if row is None:
                        skipped += 1
                        continue
                    rows.append(row)

                if skipped:
                    logger.warning(f'Пропущено невалидных записей: {skipped}')

                logger.info(f'Данные распарсились, готовим к загрузке: {len(rows)} строк')

                try:
                    logger.info(f'Загружаем данные в БД')
                    inserted = db_operations.insert_rows(rows)
                    logger.info(f'Данные загружены в БД: вставлено {inserted} из {len(rows)} строк')
                except Exception as err:
                    logger.error(f"Ошибка на этапе вставки в БД {err}")
                    raise

            except Exception as err:
                logger.error(f'День {dt:%Y-%m-%d} не загружен: {err}')
                failed_dates.append(dt)

    finally:
        db_operations.close_connection()
        cleanup_logs(LOG_DIR, KEEP_LOG_DAYS)

    if failed_dates:
        print(f"Не загружены даты: {', '.join(d.strftime('%Y-%m-%d') for d in failed_dates)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
