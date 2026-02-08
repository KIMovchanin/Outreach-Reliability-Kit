# AI Stack (Updated)

## IDE и плагины

- PyCharm / VSCode для разработки Python и интеграций.
- Базовые плагины:
  - Python/Pylance,
  - линтер/форматтер,
  - Git integration.

## Модели под задачи

- Реализация кода: модель с strong tool-use и аккуратной работой с diff.
- Рефакторинг: модель с длинным контекстом и контролем регрессий.
- Ревью: модель с фокусом на баги, edge cases, сетевые риски.
- Планирование: модель для коротких архитектурных решений и trade-offs.

## Текущий workflow в проекте

- `CLI-first`:
  - основной production-флоу реализован как CLI (`ork/scripts/*`) + модульная логика (`ork/src/ork/*`).
- `GUI wrapper`:
  - `gui/pot_gui.py` дает операторский интерфейс поверх CLI-флагов,
  - полезно для ручных запусков, диагностики и быстрых операций.

## MCP / tool stack

- `filesystem`: чтение/правка кода и конфигов.
- `git`: diff/status/история.
- `terminal`: запуск smoke-check и end-to-end команд.
- `web` (опционально): верификация внешних API и актуальных ограничений.

## Полезные правила (cursorrules/system prompts)

- Сначала логика в `src`, потом thin-wrapper в `scripts`, потом GUI контролы.
- Публичные функции и модели: typing + dataclasses.
- Явные timeout/retries/backoff для сетевых вызовов.
- Логирование с уровнями INFO/WARNING/ERROR (+ DEBUG при отладке).
- Документация должна содержать runnable команды и ограничения решения.
