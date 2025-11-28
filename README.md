# Agent Safety Kit

Набор инструментов для запуска AI-агентов в изолированной среде внутри виртуальной машины Multipass.

## Немного ликбеза, если вы не понимаете зачем это:

<img width="437" height="379" alt="image" src="https://github.com/user-attachments/assets/c3486072-e96a-4197-8b1f-d6ac228c2cc6" />

Немного ссылок (нагуглить такого можно море):

* [Qwen Coder agent destroys working builds](https://github.com/QwenLM/qwen-code/issues/354)
* [Codex keeps deleting unrelated and uncommitted files! even ignoring rejected requests](https://github.com/openai/codex/issues/4969)
* [comment: qwen-code CLI destroyed my entire project, deleted important files](https://www.reddit.com/r/DeepSeek/comments/1mmfjsl/right_now_qwen_is_the_best_model_they_have_the/)
* [Claude Code deleted my entire workspace, here's the proof](https://www.reddit.com/r/ClaudeAI/comments/1m299f5/claude_code_deleted_my_entire_workspace_heres_the/)
* [I Asked Claude Code to Fix All Bugs, and It Deleted the Whole Repo](https://levelup.gitconnected.com/i-asked-claude-code-to-fix-all-bugs-and-it-deleted-the-whole-repo-e7f24f5390c5)
* [Codex has twice deleted and corrupted my files (r/ClaudeAI comment)](https://www.reddit.com/r/ClaudeAI/comments/1nhvyu0/openai_drops_gpt5_codex_cli_right_after/)

Понятно, что "все понимают" и "у всех должны быть бэкапы" и "у вас всё должно быть в git", но пока "песочница" которую предоставляют консольные ИИ-агенты не имеет встроенных снапшотов, позволяющих откатываться назад после каждой правки, сделанной ИИ, нужен некий инструмент, который позволит сделать это самостоятельно.

## Ключевые идеи

- Агент работает только в виртуальной машине.
- Виртуальная машина запускается через Multipass (это простой инструмент от Canonnical для запуска ubuntu в виртуалке в 1 команду)
- Внутрь ВМ монтируются проектные папки из указанной пользователем директории; параллельно запускается автоматическое резервное копирование в соседнюю папку с настраиваемой частотой (по умолчанию раз в пять минут и только при изменениях), использующее `rsync` и hardlink'и для экономии места.
- Настройки виртуальной машины и агентов делаются через env-переменные, можно задавать через .env снаружи виртуалки
- Агент можно запускать, не входя в гостевую систему через `multipass shell` — фактически он всё равно исполняется внутри ВМ.

## Быстрый старт

1. Установка Multipass (потребуется sudo, работает пока только в debian-based системах):
   ```bash
   ./install_multipass.sh
   ```
   
2. Подготовьте файл окружения для будущей ВМ:
   ```bash
   cp example.env .env
   # при необходимости отредактируйте значения
   ```
   В `.env` должны быть заданы параметры машины (имя, CPU, память, диск), и параметры агентов
   
4. Создайте виртуальную машину с установленными параметрами:
   ```bash
   ./create_vm.sh
   ```

   Если ВМ уже существует, скрипт сравнит заданные в `.env` ресурсы с текущими, сообщит об отличающихся параметрах. Пока изменить параметры уже работающей машины нельзя
