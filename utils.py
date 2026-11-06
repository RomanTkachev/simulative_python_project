import ast
import glob
import logging
import os
from datetime import datetime


ATTEMPT_TYPE_MAX_LEN = 10  #ограничение varchar(10) в it_resume.grader_usage


def make_logger_for_date(dt, logger_name, log_dir):

    '''Создает логгер для индивидуального файла логов под каждую загрузку за день'''

    logger = logging.getLogger(logger_name)  
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # убираем хендлер предыдущего дня
    logger.propagate = False

    handler = logging.FileHandler(
        os.path.join(log_dir, f'{dt:%Y-%m-%d}.log'),
        encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)

    return logger


def cleanup_logs(log_dir, keep_days):

    ''' Производит очистку логово уже после загрузки; Отсавляет только 3 последних дня. Сортировка по имени файла (имя файла – это дата)'''
    if not os.path.isdir(log_dir):
        return
    
    log_files = sorted(
        glob.glob(os.path.join(log_dir, '*.log')),
        reverse=True # самые свежие логи идут первыми.
    )

    for old_log in log_files[keep_days:]:
        try:
            os.remove(old_log)
        except OSError as err:
            logging.getLogger('etl_logger').warning(
                f'Не удалось удалить лог-файл {old_log}: {err}'
            )


def parse_attempt(item, logger):
    '''Валидирует и нормализует одну запись из ответа API.

    Возвращает кортеж в порядке колонок it_resume.grader_usage
    или None, если запись невалидна и её нужно пропустить.'''

    if not isinstance(item, dict):
        logger.warning('Пропуск записи: элемент ответа не является объектом')
        return None

    try:
        passback_params_string = item.get('passback_params')
        params_dict = ast.literal_eval(passback_params_string) if passback_params_string else {}
        if not isinstance(params_dict, dict):
            params_dict = {}
    except (ValueError, SyntaxError, TypeError) as err:
        logger.warning(f'Некорректный passback_params, поля пропущены: {err}')
        params_dict = {}

    user_id = item.get('lti_user_id')
    created_at = item.get('created_at')
    if not user_id or not created_at:
        logger.warning('Пропуск записи без обязательного user_id или created_at')
        return None

    attempt_type = item.get('attempt_type')
    if isinstance(attempt_type, str) and len(attempt_type) > ATTEMPT_TYPE_MAX_LEN:
        logger.warning(f'attempt_type обрезан до {ATTEMPT_TYPE_MAX_LEN} символов: {attempt_type!r}')
        attempt_type = attempt_type[:ATTEMPT_TYPE_MAX_LEN]

    is_correct = item.get('is_correct')
    if isinstance(is_correct, bool):
        is_correct = int(is_correct)

    #порядок элементов соответствует порядку колонок в INSERT (classes.py)
    return (
        user_id,
        params_dict.get('oauth_consumer_key'),
        params_dict.get('lis_result_sourcedid'),
        params_dict.get('lis_outcome_service_url'),
        is_correct,
        attempt_type,
        created_at,
    )