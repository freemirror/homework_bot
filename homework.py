import logging
import os
import sys
import time
import traceback
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import (HomeworkStatusException, NoHomeworkToCheck,
                        NoStatusChanges, PraktikumResponseError,
                        TelegramErrors)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKEN_QUANTITY = 3

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

RETRY_TIME = 600
LAST_HOMEWORK_INDEX = 0


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        message = f'Сбой при отправке сообщения в телеграм {error}'
        raise TelegramErrors(message)


def get_api_answer(current_timestamp):
    """Получение ответа от сервиса проверки домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = f'При запросе к сервису произошла ошибка {error}'
        raise PraktikumResponseError(message)
    else:
        if response.status_code != HTTPStatus.OK:
            message = (f'Статус ответа по API не является успешным,'
                       f'{response.status_code}')
            raise PraktikumResponseError(message)
        return response.json()


def check_response(response):
    """Проверка корректности ответа от сервиса проверки домашней работы."""
    homeworks = response['homeworks']
    if type(homeworks) is not list:
        message = 'ответ от сервиса пришел не в виде списка'
        raise HomeworkStatusException(message)
    if homeworks is None:
        message = f'отсутствует ключ homeworks в ответе: {response}'
        raise HomeworkStatusException(message)
    if homeworks == []:
        message = 'в данный момент нет домашних заданий на проверке'
        raise NoHomeworkToCheck(message)
    return homeworks


def parse_status(homework):
    """Преобразование ответа сервиса в строку для отправки сообщения."""
    if homework['homework_name'] not in homework.values():
        message = (f'отсутсвует поле с именем домашней работы , '
                   f'в ответе API {homework}')
        raise HomeworkStatusException(message)
    if homework['status'] not in HOMEWORK_STATUSES:
        message = (f'недокументированный статус домашней работы, '
                   f'обнаруженный в ответе API {homework}')
        raise HomeworkStatusException(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка токенов для используемых сервисов."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if (len(tokens) == TOKEN_QUANTITY) and (None not in tokens):
        return True
    else:
        return False


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
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    cache_status = []
    if check_tokens():
        pass
    else:
        error = 'Переменные окружения не доступны в полном объеме'
        send_message(bot, error)
        logger.critical(error)
        sys.exit()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            message = parse_status(homeworks[LAST_HOMEWORK_INDEX])
            cache_status = check_cnanges(bot, message, cache_status)
            logger.info(f'Сообщение отправлено: "{message}"')
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
            current_timestamp += RETRY_TIME
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
