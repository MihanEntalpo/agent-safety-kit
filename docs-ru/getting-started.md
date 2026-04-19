# Быстрый старт

Это самый короткий практический путь к рабочему `agsekit`.

(Если короткий путь не получился, либо у вас Windows, почитайте статью [об установке](install.md))

## Содержание

- [1. Установка](#1-установка)
- [2. Создание конфига](#2-создание-конфига)
- [3. Подготовка окружения](#3-подготовка-окружения)
- [4. Добавление mount](#4-добавление-mount)
- [5. Запуск агента](#5-запуск-агента)
- [6. Проверка состояния](#6-проверка-состояния)

## 1. Установка

Создайте виртуальное окружение и установите пакет:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install agsekit
```

Также можно проделать установку через:

```shell
curl -fsSL https://agsekit.org/install.sh | sh
```

На Windows используйте PowerShell:

```powershell
irm https://agsekit.org/install.ps1 | iex
```

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

Подробное описание [конфигурации](configuration.md)

## 3. Подготовка окружения

Поднимите всё окружение одной командой:

```bash
agsekit up
```

Что будет сделано:

- подготовка зависимостей на хосте (для linux это snapd и multipass; WSL не поддерживается);
- создание VM
- подготовка VM
- установка агентов
- для Linux - установка systemd службы

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
- [Все команды](commands/README.md)
