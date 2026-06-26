# bolshoi-bot

Telegram-бот, который следит за открытием продаж льготных билетов по программе
**«Доступный Большой»** на сайте Большого театра (bolshoi.ru) и присылает
подписчикам уведомления, как только билеты вот-вот поступят в продажу.

Если вы никогда не разворачивали ботов на сервере — ничего страшного. Ниже всё
расписано по шагам.

---

## Содержание

- [Что делает бот](#что-делает-бот)
- [Команды бота](#команды-бота)
- [Как это устроено (простыми словами)](#как-это-устроено-простыми-словами)
- [Технологии](#технологии)
- [Шаг 0. Что вам понадобится](#шаг-0-что-вам-понадобится)
- [Шаг 1. Создаём бота в Telegram](#шаг-1-создаём-бота-в-telegram)
- [Шаг 2. Локальный запуск (для разработки)](#шаг-2-локальный-запуск-для-разработки)
- [Шаг 3. Деплой на обычный VPS (Ubuntu)](#шаг-3-деплой-на-обычный-vps-ubuntu)
- [Переменные окружения](#переменные-окружения)
- [Парсер и защита сайта (важно!)](#парсер-и-защита-сайта-важно)
- [Структура проекта](#структура-проекта)
- [Частые проблемы](#частые-проблемы)
- [Добавление новых программ](#добавление-новых-программ)

---

## Что делает бот

1. Раз в несколько часов парсит раздел объявлений на bolshoi.ru.
2. Найдя новое объявление о продаже льготных билетов — сразу рассылает
   предварительное уведомление всем подписчикам.
3. В день открытия продажи (за 30 минут до старта) присылает финальное
   уведомление с прямой ссылкой на покупку.
4. Отвечает на команды пользователей в чате.

## Команды бота

| Команда | Что делает |
|---|---|
| `/start`, `/подписаться` или `/subscribe` | Подписаться на уведомления |
| `/отписаться` или `/unsubscribe` | Отписаться |
| `/расписание` или `/schedule` | Ближайшие 10 предстоящих продаж |
| `/статус` или `/status` | Проверить статус подписки |
| `/помощь` или `/help` | Справка по командам |

> Команды работают и на русском, и на латинице. В меню Telegram (кнопка «/»)
> удобнее регистрировать латинские варианты — Telegram не показывает в меню
> кириллические команды.

---

## Как это устроено (простыми словами)

Бот состоит из трёх частей, которые работают вместе:

1. **Webhook-сервер.** Telegram при каждом сообщении пользователя присылает
   боту HTTP-запрос на адрес `https://ваш-домен/webhook`. Сервер на бот-стороне
   принимает этот запрос и решает, что ответить.
2. **Планировщик.** Фоновые задачи: периодически проверяет базу на новые события
   и время рассылок.
3. **Парсер.** Скачивает страницу bolshoi.ru, вытаскивает данные о спектаклях и
   складывает их в базу.

Все события и список подписчиков хранятся в базе данных **PostgreSQL**.

---

## Технологии

- Python 3.11+
- aiohttp — webhook-сервер
- Прямые HTTP-запросы к **Telegram Bot API** (без тяжёлых библиотек — просто и
  надёжно)
- httpx + BeautifulSoup4 + Playwright/Camoufox — парсинг сайта
- SQLAlchemy 2.x (async) + asyncpg — PostgreSQL
- Alembic — миграции базы данных
- APScheduler — планировщик задач
- pydantic-settings — конфигурация

---

## Шаг 0. Что вам понадобится

Для боевого запуска на сервере:

- **VPS** с Ubuntu 22.04 или 24.04 (подойдёт любой провайдер: Timeweb, Selectel,
  Hetzner, DigitalOcean и т. п.). Минимум 1 vCPU / 1 ГБ RAM.
- **Доменное имя**, привязанное к IP вашего VPS (A-запись). Домен нужен, потому
  что Telegram принимает webhook только по HTTPS с валидным сертификатом, а
  бесплатный сертификат Let's Encrypt выдаётся на домен, а не на голый IP.
- **Токен бота** из Telegram (получим на шаге 1).

Для локальной разработки достаточно Python 3.11+ и PostgreSQL на своём компьютере.

---

## Шаг 1. Создаём бота в Telegram

1. Откройте в Telegram бота [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/newbot`.
3. Придумайте имя бота (отображаемое) и username (должен заканчиваться на `bot`,
   например `bolshoi_tickets_bot`).
4. BotFather пришлёт **токен** вида `123456789:AAFooBarBazQuxQuux...`.
   Скопируйте его — это и есть `TELEGRAM_BOT_TOKEN`. Храните в секрете.

Опционально — задайте боту меню команд: отправьте BotFather `/setcommands`,
выберите бота и вставьте:

```
subscribe - Подписаться на уведомления
unsubscribe - Отписаться
schedule - Ближайшие продажи
status - Статус подписки
help - Помощь
```

---

## Шаг 2. Локальный запуск (для разработки)

```bash
# 1. Клонируем репозиторий
git clone https://github.com/AndreiSoiko/chip_bolshoi_max.git
cd chip_bolshoi_max

# 2. Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Ставим зависимости
pip install --upgrade pip
pip install -r requirements.txt

# 4. (для парсера) скачиваем браузер Camoufox
python -m camoufox fetch

# 5. Готовим конфиг
cp .env.example .env              # затем откройте .env и заполните значения

# 6. Создаём таблицы в базе
alembic upgrade head

# 7. Запускаем бота
python -m bot.main
```

Проверить парсер без записи в базу и без рассылки:

```bash
python -m parser.scraper --test
```

> Для локального запуска webhook от Telegram работать не будет (нужен публичный
> HTTPS-адрес). Локально удобно тестировать парсер и обработчики команд, а
> полноценный приём сообщений — уже на сервере (шаг 3) или через туннель вроде
> ngrok / cloudflared.

---

## Шаг 3. Деплой на обычный VPS (Ubuntu)

Здесь мы поднимаем PostgreSQL прямо на сервере, ставим бота как системную службу
и настраиваем nginx + бесплатный HTTPS-сертификат для приёма webhook.

Все команды выполняются по SSH на вашем VPS.

### 3.1. Базовые пакеты

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git \
                    postgresql postgresql-contrib nginx
```

### 3.2. Создаём базу данных PostgreSQL (локально, на этом же сервере)

```bash
sudo -u postgres psql <<'SQL'
CREATE DATABASE bolshoi_bot;
CREATE USER bot_user WITH PASSWORD 'ПРИДУМАЙТЕ_ПАРОЛЬ';
GRANT ALL PRIVILEGES ON DATABASE bolshoi_bot TO bot_user;
\c bolshoi_bot
GRANT ALL ON SCHEMA public TO bot_user;
SQL
```

Запомните имя БД (`bolshoi_bot`), пользователя (`bot_user`) и пароль — они пойдут
в `.env`. Локальный PostgreSQL слушает порт **5432**, SSL для подключения с того
же сервера не нужен.

### 3.3. Отдельный пользователь для бота

Запускать бота из-под `root` — плохая практика. Заведём отдельного пользователя:

```bash
sudo useradd -m -s /bin/bash bolshoi-bot
sudo loginctl enable-linger bolshoi-bot   # чтобы служба жила без активной сессии
```

### 3.4. Клонируем проект и настраиваем окружение

```bash
sudo -u bolshoi-bot -i        # переключаемся на пользователя бота
git clone https://github.com/AndreiSoiko/chip_bolshoi_max.git
cd chip_bolshoi_max

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m camoufox fetch       # браузер для парсера

cp .env.example .env
nano .env                      # заполняем (см. раздел «Переменные окружения»)
```

Минимальный `.env` для VPS с локальной базой:

```
TELEGRAM_BOT_TOKEN=123456789:AAFooBarBaz...
WEBHOOK_PORT=8080
WEBHOOK_URL=https://ваш-домен.ru/webhook

DB_HOST=localhost
DB_PORT=5432
DB_NAME=bolshoi_bot
DB_USER=bot_user
DB_PASSWORD=ваш_пароль_из_шага_3.2
DB_SSL_CA=

LOG_LEVEL=INFO
LOG_FILE=/var/log/bolshoi-bot/bot.log
```

> `DB_SSL_CA` оставляем пустым — для локального PostgreSQL SSL-сертификат не нужен.

Создаём таблицы:

```bash
alembic upgrade head
exit                           # выходим обратно в своего sudo-пользователя
```

### 3.5. Каталог для логов

```bash
sudo mkdir -p /var/log/bolshoi-bot
sudo chown bolshoi-bot:bolshoi-bot /var/log/bolshoi-bot
```

### 3.6. Настраиваем nginx как HTTPS-прокси

Бот слушает на `127.0.0.1:8080`, а Telegram стучится по HTTPS на 443. nginx
принимает запрос на 443 и перенаправляет внутрь на 8080.

Создаём конфиг сайта:

```bash
sudo nano /etc/nginx/sites-available/bolshoi-bot
```

Содержимое (замените `ваш-домен.ru` на свой домен):

```nginx
server {
    listen 80;
    server_name ваш-домен.ru;

    location /webhook {
        proxy_pass http://127.0.0.1:8080/webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /healthcheck {
        proxy_pass http://127.0.0.1:8080/healthcheck;
    }
}
```

Включаем сайт и проверяем конфиг:

```bash
sudo ln -s /etc/nginx/sites-available/bolshoi-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3.7. Бесплатный HTTPS-сертификат (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d ваш-домен.ru
```

Certbot сам выпустит сертификат, пропишет его в конфиг nginx и настроит
автопродление. После этого `https://ваш-домен.ru/webhook` будет доступен по HTTPS.

Проверьте, что всё живо:

```bash
curl https://ваш-домен.ru/healthcheck
# Должно вернуться: {"status": "ok", "service": "bolshoi-bot"} — но только
# после того, как сам бот будет запущен (шаг 3.8).
```

### 3.8. Запускаем бота как службу systemd

В проекте уже есть готовый файл службы `deploy/bolshoi-bot.service` — он рассчитан на пользователя `bolshoi-bot` и папку `/home/bolshoi-bot/chip_bolshoi_max` (ровно туда вы склонировали проект на шаге 3.4), поэтому копируется без изменений:

```bash
sudo cp /home/bolshoi-bot/chip_bolshoi_max/deploy/bolshoi-bot.service \
        /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable bolshoi-bot     # автозапуск при перезагрузке сервера
sudo systemctl start bolshoi-bot      # запускаем сейчас
sudo systemctl status bolshoi-bot     # проверяем, что статус active (running)
```

> Если вы клонировали проект в другую папку или под другим пользователем —
> откройте `sudo nano /etc/systemd/system/bolshoi-bot.service` и поправьте под
> себя три строки: `User`, `WorkingDirectory`, `EnvironmentFile` и `ExecStart`
> (путь к `venv/bin/python`).

При старте бот сам зарегистрирует webhook в Telegram (вызовет метод `setWebhook` с вашим `WEBHOOK_URL`). Теперь откройте своего бота в Telegram и отправьте `/start` — если пришёл ответ с подтверждением подписки, значит всё работает. 🎉

Если ответа нет — загляните в логи (команды в разделе ниже) и в [«Частые проблемы»](#частые-проблемы).

### Просмотр логов

```bash
tail -f /var/log/bolshoi-bot/bot.log
# или
sudo journalctl -u bolshoi-bot -f
```

### Обновление после изменений в коде

```bash
sudo -u bolshoi-bot -i
cd chip_bolshoi_max
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
exit
sudo systemctl restart bolshoi-bot
```

> В папке `deploy/` лежат скрипты `setup.sh` и `update.sh`, автоматизирующие
> часть этих шагов. Учтите: исходный `setup.sh` написан под Yandex Cloud и
> скачивает их SSL-сертификат — для локального PostgreSQL эта строка не нужна,
> её можно убрать. Для понимания процесса новичку проще пройти шаги вручную.

---

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен бота из @BotFather |
| `WEBHOOK_PORT` | Порт, который слушает бот локально (по умолчанию `8080`) |
| `WEBHOOK_URL` | Публичный HTTPS-адрес для webhook, напр. `https://ваш-домен.ru/webhook` |
| `BOLSHOI_NEWS_URL` | URL раздела объявлений (по умолчанию верный) |
| `PARSE_INTERVAL_HOURS` | Интервал парсинга в часах (по умолчанию `6`) |
| `NOTIFY_BEFORE_MINUTES` | За сколько минут до старта продаж слать напоминание (`30`) |
| `DB_HOST` | Хост PostgreSQL (`localhost` для локальной базы) |
| `DB_PORT` | Порт PostgreSQL (`5432` для локальной базы) |
| `DB_NAME` | Имя базы данных |
| `DB_USER` | Пользователь БД |
| `DB_PASSWORD` | Пароль БД |
| `DB_SSL_CA` | Путь к SSL-сертификату. Для локальной БД оставьте **пустым** |
| `LOG_LEVEL` | Уровень логирования (`INFO`) |
| `LOG_FILE` | Путь к лог-файлу |

> **Важно про порты Telegram.** Telegram принимает webhook только по HTTPS и
> только на портах 443, 80, 88 или 8443. Поэтому бот слушает обычный 8080
> «внутри», а наружу его публикует nginx на 443 (с сертификатом из шага 3.7).

---

## Парсер и защита сайта (важно!)

Сайт bolshoi.ru закрыт антибот-защитой (QRATOR). Чтобы её обходить, парсер
использует **Camoufox** — Firefox с защитой от отслеживания отпечатка браузера.

На практике это значит: запросы с **дата-центровых IP** (а IP большинства VPS —
именно такие) сайт может блокировать. Поэтому в проекте предусмотрен отдельный
скрипт `run_parser.py`, который удобно запускать с «домашнего» IP (например, на
вашем компьютере по расписанию), а он будет складывать найденные события в ту же
базу данных, что и бот:

```bash
python run_parser.py            # спарсить и сохранить новые события в БД
python run_parser.py --dry-run  # только показать результат, ничего не сохранять
```

Если ваш VPS не блокируется сайтом — парсер можно гонять и прямо на нём.
Проверьте это тестовым прогоном `python -m parser.scraper --test`.

---

## Структура проекта

```
chip_bolshoi_max/
├── bot/
│   ├── main.py           # точка входа: webhook-сервер + старт планировщика
│   ├── handlers.py       # обработчики команд пользователя
│   ├── notifications.py  # клиент Telegram Bot API, шаблоны и рассылка
│   └── scheduler.py      # фоновые задачи (APScheduler)
├── parser/
│   ├── scraper.py        # загрузка страниц bolshoi.ru (Camoufox)
│   └── extractor.py      # разбор HTML → структура события
├── db/
│   ├── __init__.py       # подключение к БД + фабрика сессий
│   ├── models.py         # модели Event и Subscriber
│   ├── repository.py     # CRUD-операции
│   └── migrations/       # миграции Alembic
├── deploy/
│   ├── bolshoi-bot.service
│   ├── setup.sh
│   └── update.sh
├── config.py             # конфигурация (pydantic-settings)
├── alembic.ini
├── requirements.txt
├── run_parser.py         # запуск парсера отдельно от бота
└── .env.example
```

---

## Частые проблемы

**Бот не отвечает на команды.** Проверьте, что webhook зарегистрирован. Откройте
в браузере (подставив свой токен):
`https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo` — поле `url` должно
совпадать с вашим `WEBHOOK_URL`, а `pending_update_count` не должен расти.

**`Wrong response from the webhook` / Telegram не шлёт обновления.** Убедитесь,
что сертификат валиден (`curl https://ваш-домен/healthcheck` отвечает), а порт 443
открыт в фаерволе провайдера.

**Ошибка подключения к базе.** Проверьте `DB_HOST=localhost`, `DB_PORT=5432`,
правильность пароля и что служба PostgreSQL запущена:
`sudo systemctl status postgresql`.

**Парсер ничего не находит / блокировки.** См. раздел
[«Парсер и защита сайта»](#парсер-и-защита-сайта-важно) — вероятно, IP сервера
блокируется. Запускайте `run_parser.py` с домашнего IP.

**Смотреть, что именно упало.** Логи: `sudo journalctl -u bolshoi-bot -f`.

---

## Добавление новых программ

Чтобы отслеживать, например, «Пушкинскую карту»:

1. Добавьте ключевые слова в `parser/extractor.py` → `PROGRAM_KEYWORDS`.
2. Добавьте ключевые слова в `parser/scraper.py` → `KEYWORDS`.
3. Если нужна новая колонка в базе — создайте миграцию:
   `alembic revision --autogenerate -m "add pushkin card"`, затем
   `alembic upgrade head`.
