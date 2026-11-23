# Различные технчиеские скрипты agsekit

## setup-agsekit-org.yml — настройка хоста установщиков

Плейбук подготавливает Debian/Ubuntu VPS для `https://agsekit.org/install.sh`
и `https://agsekit.org/install.ps1`: устанавливает Nginx и Certbot, создаёт
пользователя `agsekit`, каталог публикации
`/home/agsekit/agsekit.org/www` и выпускает сертификат Let's Encrypt для
`agsekit.org` с контактным адресом `mihanentalpo@yandex.ru`. Корень домена
перенаправляется на GitHub-репозиторий проекта, а файлы установщиков остаются
доступны по своим прямым URL.

Скопируйте `inventory.example.yaml` в `inventory.yaml`, укажите путь к
приватному ключу для доступа к VPS и публичную часть
`AGSEKIT_ORG_SSH_PRIVATE_KEY` из GitHub Actions, затем запустите:

```shell
ansible-playbook -i scripts/inventory.yaml scripts/setup-agsekit-org.yml
```

Перед запуском A/AAAA-запись `agsekit.org` должна указывать на VPS, а порты
80 и 443 должны быть доступны извне.

## install/install.sh - универсальный скрипт установки для `curl | bash`

Работает в:

* Linux
  * debian
  * arch
* MacOS

Что делает:

* Создаёт venv
* Устанавливает в него agsekit
* Добавляет agsekit в PATH для запуска откуда угодно

## install/install.ps1 - Windows-скрипт установки для PowerShell

Работает в native Windows PowerShell. WSL не поддерживается.

Что делает:

* Проверяет наличие Python 3.9+
* Создаёт venv
* Устанавливает в него agsekit
* Создаёт `agsekit.cmd`
* Добавляет wrapper-каталог в пользовательский PATH
