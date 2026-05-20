# Sumire Telegram Web App

Telegram Web App service assistant for `kawaii_manga`.

## What It Does

- Handles simple anime/manga search in Django without Gemini.
- Uses `https://bot.kawaii.uz/api/v1/search/` as the live catalog source.
- Uses Gemini only as an intent parser when backend rules do not understand the user text.
- Creates support tickets in Django for bugs, payment issues, complaints, and broken content.
- Notifies staff admins in Telegram when `BOT_TOKEN` and admin `Profile` records are configured.

## Local Backend

```powershell
copy .env.example .env
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py runserver
```

## Local Frontend

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

For local frontend development, keep:

```env
VITE_API_BASE_URL=http://localhost:8000
```

In production, leave `VITE_API_BASE_URL` empty if frontend and backend are served from the same domain.

## Environment

Important backend variables:

```env
DEBUG=False
SECRET_KEY=change-me
ALLOWED_HOSTS=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com
DATABASE_URL=postgres://user:password@host:5432/dbname
BOT_TOKEN=telegram-bot-token
GEMINI_API_KEY=gemini-api-key
```

SQLite is fine for local development. For a real server, use PostgreSQL for service data: admin profiles, tickets, ticket messages, limits, and logs. The anime catalog should stay external and live on `bot.kawaii.uz`.

## Admin Binding

Create or update a staff admin linked to Telegram:

```powershell
venv\Scripts\python.exe manage.py create_admin_tg --username admin --telegram-id 123456789 --password strong-password --owner
```

## Build Frontend

```powershell
cd frontend
npm run build
```
