# Тесты для Claude Bot

## Установка зависимостей

```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
```

## Запуск тестов

Запустить все тесты:
```bash
pytest
```

Запустить с подробным выводом:
```bash
pytest -v
```

Запустить конкретный файл:
```bash
pytest test_handlers.py
pytest test_claude_client.py
pytest test_main.py
```

Запустить с покрытием кода:
```bash
pytest --cov=. --cov-report=html
```

## Структура тестов

- `test_handlers.py` - тесты для обработчиков сообщений
  - Проверка прав доступа пользователей
  - Проверка упоминаний бота
  - Тесты команд /start, /clear, /help
  - Тесты обработки сообщений в личке и группах
  
- `test_claude_client.py` - тесты для клиента Claude API
  - Инициализация клиента
  - Управление историей диалогов
  - Сохранение/загрузка диалогов
  - Обработка ошибок API
  
- `test_main.py` - тесты для главного модуля
  - Инициализация бота
  - Работа с прокси
  - Обработка ошибок
