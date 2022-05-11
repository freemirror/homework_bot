import logging
import os
import sys
import time
import traceback
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (HomeworkStatusException, NoHomeworkToCheck,
                        NoStatusChanges, PraktikumResponseError,
                        TelegramErrors)
from settings import (ENDPOINT, HEADERS, HOMEWORK_STATUSES,
                      LAST_HOMEWORK_INDEX, RETRY_TIME)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        message = f'Сбой при отправке сообщения в телеграм {error}'
        raise TelegramErrors(message)


def get_api_answer(current_timestamp):
    """Получение ответа от сервиса проверки домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    HEADERS['Authorization'] = f'{HEADERS["Authorization"]}{PRACTICUM_TOKEN}'
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = f'При запросе к сервису произошла ошибка {error}'
        raise PraktikumResponseError(message)
    if response.status_code != HTTPStatus.OK:
        message = (f'Статус ответа по API не является успешным,'
                   f'{response.status_code}')
        raise PraktikumResponseError(message)
    return response.json()


def check_response(response):
    """Проверка корректности ответа от сервиса проверки домашней работы."""
    if type(response) is not dict:
        message = 'ответ от сервиса не является словарем'
        raise TypeError(message)
    if response.get('homeworks') is None:
        message = f'отсутствует ключ homeworks в ответе: {response}'
        raise HomeworkStatusException(message)
    if type(response['homeworks']) is not list:
        message = 'значение запроса по ключу "homeworks" не является списком'
        raise TypeError(message)
    if not response['homeworks']:
        message = 'в данный момент изменений нет'
        raise NoHomeworkToCheck(message)
    return response['homeworks']


def parse_status(homework):
    """Преобразование ответа сервиса в строку для отправки сообщения."""
    if type(homework) is not dict:
        message = 'сведения о домашней работе не являются словарем'
        raise TypeError(message)
    try:
        homework_name = homework['homework_name']
    except KeyError as error:
        message = (f'отсутсвует поле с именем домашней работы , '
                   f'в ответе API {error}')
        raise KeyError(message)
    try:
        homework_status = homework['status']
    except KeyError as error:
        message = (f'отсутсвует поле со статусом домашней работы, '
                   f'в ответе API {error}')
        raise KeyError(message)
    if homework['status'] not in HOMEWORK_STATUSES.keys():
        message = (f'недокументированный статус домашней работы, '
                   f'обнаруженный в ответе API {homework}')
        raise HomeworkStatusException(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка токенов для используемых сервисов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def check_cnanges(bot, message, cache_status):
    """Проверка статуса ошибки или домашней работы на изменение."""
    if message != cache_status:
        send_message(bot, message)
        cache_status = message
        return cache_status
    else:
        message = 'Статус домашнего задания/ошибки не изменился'
        raise NoStatusChanges(message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Переменные окружения не доступны в полном объеме')
        sys.exit()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    cache_status = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks[LAST_HOMEWORK_INDEX])
            cache_status = check_cnanges(bot, message, cache_status)
            logger.info(f'Сообщение отправлено: "{message}"')
            current_timestamp = int(time.time())
        except PraktikumResponseError as error:
            logger.error(error)
            cache_status = check_cnanges(bot, error, cache_status)
        except HomeworkStatusException as error:
            logger.error(error)
            cache_status = check_cnanges(bot, error, cache_status)
        except NoHomeworkToCheck as error:
            logger.info(error)
        except TelegramErrors as error:
            logger.error(error)
        except NoStatusChanges as message:
            logger.debug(message)
        except Exception:
            message = f'Сбой в работе программы\n{traceback.format_exc()}'
            logger.error(message)
            cache_status = check_cnanges(bot, message, cache_status)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
