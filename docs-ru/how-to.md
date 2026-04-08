# Практические How-To

На этой странице собраны короткие практические рецепты, которые полезны на раннем этапе использования.

## OpenAI-compatible API

Конкретные флаги зависят от CLI агента, но общий паттерн всегда один:

1. задать provider-specific defaults в профиле агента или передавать их в runtime;
2. не хранить секреты в репозитории;
3. использовать те же флаги агента, что и без `agsekit`.

Связанные материалы:

- [Поддерживаемые агенты](agents.md)
- [run](commands/run.md)

## Работа в ограниченной сети

Используйте один из подходов:

- `proxychains`, когда runtime должен работать через proxy-aware command layer;
- direct mode `http_proxy`, когда у вас уже есть готовый HTTP proxy;
- upstream mode `http_proxy`, когда `agsekit` сам поднимает временный `privoxy` внутри VM.

Не включайте effective `proxychains` и effective `http_proxy` одновременно для одного и того же `run`.

## Использование `proxychains`

Типовой сценарий:

```bash
agsekit install-agents qwen --proxychains socks5://127.0.0.1:1080
cd /path/to/project
agsekit run --proxychains socks5://127.0.0.1:1080 qwen
```

## Использование `http_proxy`

Пример direct mode:

```yaml
vms:
  agent-ubuntu:
    http_proxy:
      url: http://127.0.0.1:18881
```

Пример upstream mode:

```yaml
vms:
  agent-ubuntu:
    http_proxy: socks5://127.0.0.1:8181
```

## Использование `portforward`

Опишите forwarding rules в конфиге и держите их поднятыми так:

```bash
agsekit portforward
```

На Linux это же поведение можно держать в фоне через интеграцию с `systemd`.

## См. также

- [Сеть и прокси](networking.md)
- [Сетевые команды](commands/networking.md)
- [systemd](commands/systemd.md)
