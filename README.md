# 🤖 Telegram Feedback Mini App (Django + HTMX)

Инструмент для сбора заявок и обратной связи через Telegram Mini App с админ-панелью на Django и поддержкой PostgreSQL.

## 🌟 Основные функции
* **Neo-Brutalism UI**: Современный интерфейс на Tailwind CSS с использованием шрифта Unbounded.
* **HTMX Powered**: Отправка форм и обновление истории без перезагрузки страницы.
* **Haptic Feedback**: Тактильный отклик (вибрация) при взаимодействии с приложением через Telegram WebApp SDK.
* **PostgreSQL Support**: Полная готовность к деплою на Render с использованием надежной базы данных.
* **Anti-Spam**: Ограничение на частоту отправки сообщений (60 секунд).
* **Django Admin**: Удобное управление заявками и ответами пользователям.

## 🛠 Стек технологий
* **Backend**: Django 
* **Frontend**: HTMX, Tailwind CSS, JavaScript (Telegram WebApp SDK)
* **Database**: PostgreSQL (Production), SQLite (Local)
* **Server**: Gunicorn (для Render)

## 🚀 Как запустить локально

1. **Клонируйте репозиторий:**
   ```bash
   git clone [https://github.com/devvesama/tg-feedback-bot.git](https://github.com/devvesama/tg-feedback-bot.git)
   cd tg-feedback-bot
   ```

2. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Настройте .env:**
   Создайте файл `.env` и добавьте:
   ```env
   BOT_TOKEN=ваш_токен
   ADMIN_ID=ваш_id
   SECRET_KEY=ваш_секретный_ключ_django
   DATABASE_URL=ваша_ссылка_на_db (для postgres)
   ```

4. **Запустите миграции и сервер:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## ☁️ Деплой (Render)
* **Build Command**: `pip install -r requirements.txt && python manage.py migrate`
* **Start Command**: `gunicorn core.wsgi:application`
```

## 👥 Несколько админов (главный + дополнительные)
Теперь админов можно добавлять **прямо в Django Admin**:

1. Откройте `Django Admin -> Profiles -> Add profile`.
2. Укажите:
   - `Admin nick` (ник админа),
   - `Parol` (пароль),
   - `telegram_id` (его Telegram ID),
   - флаг `Главный админ (superuser)` — только для owner.
3. Сохраните.

После сохранения автоматически создаётся/обновляется Django-пользователь:
- `is_staff=True` для любого админа,
- `is_superuser=True` только для главного админа (owner),
- привязка Telegram ID хранится в `Profile`.

Важно: один Telegram ID может быть привязан только к одному администратору.

> Для автоматизации можно и дальше использовать `python manage.py create_tg_admin ...`, но это уже не обязательно.

