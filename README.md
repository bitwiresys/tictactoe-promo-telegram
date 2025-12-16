# Tic-Tac-Toe (Player vs Computer) + Promo + Telegram
 
## О проекте
Web-игра «Крестики‑нолики» (игрок vs компьютер) с выдачей 5‑значного промокода при победе и надёжной отправкой уведомлений в Telegram через outbox + отдельный worker.

## Реализация требований ТЗ
- Backend: Python 3.10, FastAPI, async SQLAlchemy, Postgres.
- Docker + docker-compose.
- Alembic миграции.
- ruff (lint+format), mypy strict.
- pytest + coverage gate ≥ 75%.
- Защита от race conditions:
  - `SELECT ... FOR UPDATE` по игре.
  - идемпотентность на `POST /moves` (`Idempotency-Key`) + DB-хранилище ответов.
- Надёжная отправка Telegram: outbox_events + отдельный worker с `FOR UPDATE SKIP LOCKED`.
- Health endpoints: `/health`, `/ready`.
- Структурированные JSON-логи + `X-Request-Id`.

## Допущения (если ТЗ неоднозначно)
- **Символы**: игрок всегда `X`, компьютер `O` (как в ТЗ по умолчанию). В API параметр `player_symbol` оставлен, но принимается только `X`.
- **Ничья**: Telegram не отправляем (как допускает ТЗ).
- **Антиабуз**: включён флагом `PROMO_LIMITS_ENABLED`.
  - Лимит 1 промокод / 24 часа на `client_id`.
  - Лимит 1 промокод / 24 часа на IP применяется только если IP доступен.
- **Telegram**: если токен/чат не заданы — события всё равно пишутся в outbox только при победе/поражении, но worker помечает такие события как `failed` с ретраями (поведение безопасно для продакшена).

## Структура репозитория
```
.
├─ backend/
│  ├─ app/
│  │  ├─ api/v1/...
│  │  ├─ domain/...
│  │  ├─ models/...
│  │  ├─ services/...
│  │  ├─ main.py
│  │  └─ worker.py
│  ├─ alembic/
│  │  ├─ env.py
│  │  └─ versions/0001_initial.py
│  ├─ requirements.txt
│  ├─ requirements-dev.txt
│  ├─ pyproject.toml
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  ├─ package.json
│  └─ Dockerfile
├─ docker-compose.yml
├─ .env.example
└─ .github/workflows/ci.yml
```

## Переменные окружения (ENV)
Смотри `.env.example`.

Минимально для локального запуска:
- `DATABASE_URL`
- `ALEMBIC_DATABASE_URL`
- `CORS_ORIGINS`

Для Telegram:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Для worker:
- `OUTBOX_BATCH_SIZE`
- `OUTBOX_POLL_INTERVAL_SECONDS`
- `OUTBOX_PROCESSING_TIMEOUT_SECONDS`

## Локальный запуск (Docker Compose)
1) Создай `.env` из примера:
```
cp .env.example .env
```
2) Запусти сервисы:
```
docker compose up --build
```

Compose поднимет:
- `db` (Postgres)
- `migrate` (alembic upgrade head)
- `api` (FastAPI)
- `worker` (обработчик outbox)
- `web` (Vite dev server)

URLs:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`, `http://localhost:8000/ready`

## Миграции вручную
```
docker compose run --rm migrate
```

## Проверки качества (локально)
Backend (внутри `backend/`):
```
ruff format --check .
ruff check .
mypy --strict app
pytest
```

## Деплой и получение публичной HTTPS ссылки
Вариант (простой и воспроизводимый):

### 1) Backend + Worker + Postgres на Render
- Создай Render **PostgreSQL**.
- Создай 2 Render сервиса (Docker):
  - `api` (Dockerfile: `backend/Dockerfile`, старт: `uvicorn ...` уже в CMD, Render даёт `PORT`)
  - `worker` (тот же Dockerfile, команду переопредели на `python -m app.worker`)
- Добавь ENV в оба сервиса:
  - `DATABASE_URL` (asyncpg)
  - `ALEMBIC_DATABASE_URL` (psycopg2)
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (по необходимости)
  - `PROMO_LIMITS_ENABLED=true`
- Прогони миграции:
  - можно отдельным “one-off job” на Render: `alembic upgrade head`

### 2) Frontend на Vercel/Netlify
- Укажи `VITE_API_BASE_URL=https://<render-api-domain>`
- Собери и задеплой.

Итог: получишь публичную HTTPS ссылку на фронтенд.
