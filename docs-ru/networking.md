# Сеть и прокси

`agsekit` поддерживает три основных сетевых helper'а:

- `proxychains`
- `http_proxy`
- SSH `portforward`

## proxychains

Используйте `proxychains`, когда installer или агент должен работать через SOCKS или proxy-aware wrapper.

Его можно задавать:

- на уровне VM в конфиге;
- на уровне команды через `--proxychains scheme://host:port`;
- отключать на один запуск через `--proxychains ""`.

## http_proxy

`http_proxy` может резолвиться как из VM, так и из agent configuration.

### Direct Mode

Вы передаёте готовый URL HTTP proxy, а `agsekit` просто выставляет `HTTP_PROXY` и `http_proxy` в окружении агента.

### Upstream Mode

Вы передаёте URL upstream proxy, а `agsekit` запускает временный `privoxy` внутри VM на время конкретного run. Если listening port явно не задан, он выбирается из `global.http_proxy_port_pool`.

## Взаимное исключение

Для одного `run` effective `http_proxy` и effective `proxychains` взаимоисключают друг друга. `agsekit` завершает запуск с ошибкой, а не пытается угадывать, какой транспорт важнее.

## Port Forwarding

`agsekit portforward` поддерживает SSH tunnels для настроенных VM и периодически перечитывает конфиг, чтобы переподключать forwards при изменении правил.

## Типовые сценарии

- corporate SOCKS proxy для доступа к моделям
- direct HTTP proxy для OpenAI-compatible API
- стабильный локальный tunnel для доступа к сервисам из guest на host

## См. также

- [Сетевые команды](commands/networking.md)
- [run](commands/run.md)
- [Конфигурация](configuration.md)
