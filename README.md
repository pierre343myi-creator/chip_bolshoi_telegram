# bolshoi-bot

Бот для мессенджера МАКС, отслеживающий открытие продаж льготных билетов
по программе **«Доступный Большой»** на сайте Большого театра.

## Что делает бот

1. Парсит раздел объявлений bolshoi.ru каждые 6 часов.
2. При обнаружении нового объявления — немедленно рассылает предварительное уведомление всем подписчикам.
3. В день открытия продажи, за 30 минут до старта, рассылает финальное уведомление с прямой ссылкой на покупку.
4. Отвечает на команды пользователей.

## Команды бота

| Команда | Описание |
|---|---|
| `/подписаться` или `/start` | Подписаться на уведомления |
| `/отписаться` или `/стоп` | Отписаться |
| `/расписание` | Ближайшие 10 предстоящих продаж |
| `/статус` | Проверить статус подписки |
| `/помощь` | Справка по командам |

## Стек

- Python 3.11+
- aiohttp — webhook-сервер
- httpx + BeautifulSoup4 — парсинг сайта
- SQLAlchemy 2.x (async) + asyncpg — PostgreSQL
- Alembic — миграции
- APScheduler — планировщик задач
- pydantic-settings — конфигурация

## Требования

- Python 3.11+
- PostgreSQL кластер (Yandex Managed Service for PostgreSQL)
- Публичный HTTPS-адрес ВМ для webhook

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните все значения:

```
MAX_BOT_TOKEN        — токен бота из @BotFather в МАКС
MAX_GROUP_ID         — ID группы (если нужен)
WEBHOOK_PORT         — порт webhook-сервера (по умолчанию 8080)
WEBHOOK_URL          — публичный URL вашей ВМ (https://your-ip/webhook)

BOLSHOI_NEWS_URL     — URL раздела объявлений (по умолчанию верный)
PARSE_INTERVAL_HOURS — интервал парсинга в часах (по умолчанию 6)
NOTIFY_BEFORE_MINUTES — за сколько минут до открытия слать уведомление (30)

DB_HOST              — хост PostgreSQL кластера Yandex Cloud
DB_PORT              — порт (6432 для pgbouncer)
DB_NAME              — имя базы данных
DB_USER              — пользователь БД
DB_PASSWORD          — пароль
DB_SSL_CA            — путь к SSL-сертификату (~/.postgresql/root.crt)

LOG_LEVEL            — уровень логирования (INFO)
LOG_FILE             — путь к лог-файлу
```

## Локальный запуск (разработка)

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # заполнить .env
alembic upgrade head          # создать таблицы в БД

python -m bot.main            # запустить бота
```

Тестовый прогон парсера без БД и рассылки:

```bash
python -m parser.scraper --test
```

## Деплой на Yandex Cloud VM

### Подготовка ВМ (один раз, от sudo-пользователя)

```bash
# Создать пользователя бота
sudo useradd -m -s /bin/bash bolshoi-bot
sudo loginctl enable-linger bolshoi-bot

# Создать каталог логов
sudo mkdir -p /var/log/bolshoi-bot
sudo chown bolshoi-bot:bolshoi-bot /var/log/bolshoi-bot

# Разрешить перезапуск только своего сервиса
echo "bolshoi-bot ALL=(ALL) NOPASSWD: /bin/systemctl restart bolshoi-bot, /bin/systemctl status bolshoi-bot" \
  | sudo tee /etc/sudoers.d/bolshoi-bot
```

### Настройка SSH-ключа для GitHub (от пользователя bolshoi-bot)

```bash
sudo -u bolshoi-bot bash
ssh-keygen -t ed25519 -C "bolshoi-bot@yandex-cloud" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub     # добавить в GitHub → репозиторий → Settings → Deploy keys
```

`~/.ssh/config`:
```
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519
```

### Первый деплой (от пользователя bolshoi-bot)

```bash
cd /home/bolshoi-bot
git clone git@github.com:YOUR_ORG/bolshoi-bot.git
cd bolshoi-bot

cp .env.example .env          # заполнить реальными значениями
bash deploy/setup.sh          # venv + pip + SSL cert + alembic migrate

# Затем от sudo-пользователя:
sudo cp deploy/bolshoi-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bolshoi-bot
sudo systemctl start bolshoi-bot
sudo systemctl status bolshoi-bot
```

### SSL-сертификат для Yandex Managed PostgreSQL

```bash
mkdir -p ~/.postgresql
wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" \
     -O ~/.postgresql/root.crt --quiet
chmod 0600 ~/.postgresql/root.crt
```

Путь указывается в `DB_SSL_CA=/home/bolshoi-bot/.postgresql/root.crt`.

### Обновление (после git push)

```bash
sudo -u bolshoi-bot bash -c "cd /home/bolshoi-bot/bolshoi-bot && bash deploy/update.sh"
```

### Просмотр логов

```bash
tail -f /var/log/bolshoi-bot/bot.log
# или
sudo journalctl -u bolshoi-bot -f
```

## Структура проекта

```
bolshoi-bot/
├── bot/
│   ├── main.py           # точка входа, webhook-сервер, старт планировщика
│   ├── handlers.py       # обработчики команд
│   ├── notifications.py  # MAX API клиент, шаблоны уведомлений, broadcast
│   └── scheduler.py      # APScheduler задачи
├── parser/
│   ├── scraper.py        # HTTP-запросы + фильтрация списка новостей
│   └── extractor.py      # парсинг HTML страницы объявления → структура
├── db/
│   ├── __init__.py       # engine + session factory
│   ├── models.py         # SQLAlchemy модели Event, Subscriber
│   ├── repository.py     # async CRUD
│   └── migrations/       # Alembic
├── deploy/
│   ├── bolshoi-bot.service
│   ├── setup.sh
│   └── update.sh
├── config.py             # pydantic-settings
├── alembic.ini
├── requirements.txt
└── .env.example
```

## Добавление новых программ

Чтобы отслеживать, например, «Пушкинскую карту»:
1. Добавить ключевые слова в `parser/extractor.py` → `PROGRAM_KEYWORDS`
2. Добавить ключевые слова в `parser/scraper.py` → `KEYWORDS`
3. Создать миграцию Alembic если нужна новая колонка: `alembic revision --autogenerate -m "add pushkin card"`
