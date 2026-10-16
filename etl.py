import requests 
import psycopg2 
from psycopg2.extras import execute_values
import ast
import logging 
import os 
from datetime import datetime, timedelta
from classes import DatabaseConnection, DatabaseOperations
from dotenv import load_dotenv
from pathlib import Path
from utils import make_logger_for_date, cleanup_logs


#Загружаем переменные окружения
load_dotenv()

IT_RESUME_API_URL = os.environ.get('IT_RESUME_API_URL')

#Настраиваем логирование

LOG_DIR = Path(os.environ.get('APP_LOG_DIR', './logs'))
LOG_DIR.mkdir(parents=True, exist_ok=True)

KEEP_LOG_DAYS = 3  #сколько дней храним логи

conn = DatabaseConnection.get_instance().get_connection()
db_operations = DatabaseOperations(conn)

current_last_date = db_operations.check_last_date()
print(current_last_date)

#Генерируем список дат для демонстрации загрузки (когда будет airflow – заменим на логическую дату)

START_DT = current_last_date if current_last_date else datetime(2026,5,23,0,0,0,0,None) #для демонстрации при пустой БД берем 10 дней мая для загрузки
END_DT = datetime(2026,6,1,0,0,0,0,None) #ограничения API, данные доступны только до июня 2026 года

days = (END_DT - START_DT).days 
dates = [START_DT + timedelta(days=i) for i in range(days)]

for dt in dates: 

    logger = make_logger_for_date(dt, 'etl_logger', LOG_DIR)

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

    attempts = []

    for i in response.json():

        try:
            passback_params_string = i.get('passback_params')
            params_dict = ast.literal_eval(passback_params_string) if passback_params_string else {}

            attempt= {
                'user_id':i.get('lti_user_id', None),
                'oauth_consumer_key': params_dict.get('oauth_consumer_key', None),
                'lis_result_sourcedid': params_dict.get('lis_result_sourcedid', None),
                'lis_outcome_service_url': params_dict.get('lis_outcome_service_url', None),
                'is_correct': i.get('is_correct', None),
                'attempt_type': i.get('attempt_type', None),
                'created_at': i.get('created_at', None)
            }

            attempts.append(attempt)

        except Exception as err:
            logger.error(f"Ошибка на этапе парсинга {err}")
            raise
    

    cols_db_table = [
        'user_id',
        'oauth_consumer_key',
        'lis_result_sourcedid',
        'lis_outcome_service_url',
        'is_correct',
        'attempt_type',
        'created_at'
    ]

    logger.info(f'Данные распарсились, готовим к загрузке')

    rows = [tuple(d.get(col) for col in cols_db_table) for d in attempts]

    try:
        logger.info(f'Загружаем данные в БД')
        inserted = db_operations.insert_rows(rows)
        logger.info(f'Данные загружены в БД: вставлено {inserted} из {len(rows)} строк')
    except Exception as err:
        logger.error(f"Ошибка на этапе вставки в БД {err}")

db_operations.close_connection()

cleanup_logs(LOG_DIR, KEEP_LOG_DAYS)




