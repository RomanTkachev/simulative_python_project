import glob
import logging
import os
from datetime import datetime


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