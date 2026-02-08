# AI Stack (Blitz)

## IDE и плагины

- PyCharm Professional:
  - удобно для Python-интеграций, отладки и инспекций типов.
- VSCode (альтернатива):
  - Python, Pylance, Ruff, EditorConfig, GitLens.
- Минимум для качества:
  - форматирование/линт в pre-commit,
  - статическая проверка типов (`mypy` поэтапно).

## Модели под задачи

- Coding/implementation: сильная codegen-модель с хорошим tool-use.
- Refactoring: модель с длинным контекстом и аккуратной работой по diff.
- Code review/risk checks: модель, ориентированная на дефекты и edge cases.
- Planning/architecture notes: модель с сильным reasoning и краткой структурной подачей.

## MCP (если используется)

- `filesystem`: безопасное чтение/редактирование проекта.
- `git`: проверка diff, коммитов, истории.
- `browser/web`: документация API/SDK, верификация актуальных ограничений.
- `terminal/exec`: быстрые smoke-checks и запуск CLI.

## Полезные cursorrules/системные инструкции

- Стиль кода:
  - Python 3.11+, typing в публичных функциях, dataclasses для DTO.
- Надежность:
  - явные timeout, bounded retries, понятные ошибки и logging.
- Архитектура:
  - разделять domain logic / transport / CLI слой.
- Тестируемость:
  - self-check/smoke режимы для быстрого CI даже без тяжелых тестов.
- DX:
  - короткий README с runnable-командами и ограничениями решения.
