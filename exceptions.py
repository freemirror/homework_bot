class PraktikumResponseError(Exception):
    """Ошибки полученные при отправке запроса к сервису домашней работы."""
    pass


class HomeworkStatusException(Exception):
    """Ошибки при разборе ответа от сервиса домашней работы."""
    pass


class NoHomeworkToCheck(Exception):
    """Ошибка отсутсвия задания на проверку."""
    pass


class TelegramErrors(Exception):
    """Ошибки про попытке отправить сообщение через телеграм бота."""
    pass


class NoStatusChanges(Exception):
    """Статус домашней работы или ошибки не изменился."""
    pass
