# Быстрый старт

Это самый короткий практический путь к рабочему `agsekit`.

## 1. Установка

Создайте виртуальное окружение и установите пакет:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install agsekit
```

Установка Multipass на хост позже делается через `agsekit prepare` или `agsekit up`.

## 2. Создание конфига

Рекомендуемый путь:

```bash
agsekit config-gen
```

Альтернатива:

```bash
agsekit config-example
```

После этого отредактируйте `~/.config/agsekit/config.yaml` или передавайте свой путь через `--config`.

## 3. Подготовка окружения

Поднимите всё окружение одной командой:

```bash
agsekit up
```

Это может включать:

- подготовку зависимостей на хосте;
- создание VM;
- подготовку VM;
- установку агентов;
- Linux-only systemd setup для `portforward`.

## 4. Добавление mount

Добавьте директорию проекта:

```bash
agsekit addmount /path/to/project
```

CLI умеет подставлять разумные значения по умолчанию для пути в VM, backup path, интервала и cleanup policy.

## 5. Запуск агента

Перейдите в директорию проекта и запустите агента:

```bash
cd /path/to/project
agsekit run qwen
```

Если бэкапы включены и снапшотов ещё нет, перед запуском агента будет создан первый initial backup.

## 6. Проверка состояния

Полезные команды после старта:

```bash
agsekit status
agsekit shell
agsekit ssh agent-ubuntu
```

## См. также

- [Конфигурация](configuration.md)
- [Агенты](agents.md)
- [Сеть](networking.md)
- [Индекс команд](commands/README.md)
