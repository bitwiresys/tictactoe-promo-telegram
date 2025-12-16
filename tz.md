## ТЗ на готовый продукт: web-игра «Крестики‑нолики» (игрок vs компьютер) + промокод + Telegram-уведомления

### 0) Результат проекта
- Публичная **рабочая ссылка** на игру (HTTPS).
- Репозиторий с кодом (backend + frontend + infra) и понятным README.
- Развёртывание воспроизводимо из `docker compose` и/или через выбранный хостинг (Render/Fly.io/Railway/Vercel и т.д.).
- Telegram-бот настроен для теста (в проде токены через ENV).

---

## 1) Продуктовые требования

### 1.1 Сценарий пользователя
1) Пользователь открывает страницу игры.
2) Видит приветственный экран (короткое описание + CTA «Начать игру»).
3) Играет в крестики-нолики против компьютера.
4) В конце партии:
   - **Победа игрока** → показываем **рандомный 5‑значный промокод**, кнопка «Скопировать», CTA «Сыграть ещё». Параллельно отправляем в Telegram:  
     `Победа! Промокод выдан: 12345`
   - **Поражение игрока** → показываем экран «Вы проиграли» + CTA «Сыграть ещё». Параллельно отправляем в Telegram:  
     `Проигрыш`
   - **Ничья** (обязательная логика, даже если не упомянута) → экран «Ничья» + CTA «Сыграть ещё». Telegram не обязателен (по умолчанию не шлём), но возвращаем статус.

### 1.2 Визуал и UX (женская аудитория 25–40)
Требования к UI/UX:
- Тон: мягкий, поддерживающий, “уютный”, без токсичных формулировок.
- Стиль: пастель/нейтральные оттенки, аккуратные скругления, читаемая типографика, больше воздуха.
- Обязательно:
  - мобильная адаптация (360px+), удобные тап-зоны;
  - понятная индикация чей ход;
  - анимации/микроэффекты умеренно (подсветка клетки/линии победы, лёгкий fade);
  - кнопка «Скопировать промокод» + toast «Скопировано».

---

## 2) Нефункциональные требования (качество “production ready”)

### 2.1 Backend (обязательное)
- Python **3.10**
- **Async**-архитектура (FastAPI + async SQLAlchemy)
- **PostgreSQL** как единственный источник истины
- **Docker** / docker-compose
- **mypy strict**
- **ruff** (lint + format), соблюдение PEP8
- Тесты: pytest (+pytest-asyncio), покрытие **≥ 75%** (линиями; желательно + ветвления)
- Отсутствие race conditions: конкурирующие запросы не ломают состояние партии, не создают дубли промокодов и Telegram-сообщений

### 2.2 Production-готовность
- Конфигурация только через ENV, секреты не в репозитории
- Нормальные health endpoints (`/health`, `/ready`)
- Структурированные логи (JSON), request_id
- Миграции Alembic
- CI: линтеры/типы/тесты/coverage-gate
- Telegram-уведомления доставляются **надёжно** (не “best effort” в одном запросе)

---

## 3) Архитектура решения

### 3.1 Компоненты
1) **Frontend** (SPA или Next.js) — UI/UX.
2) **Backend API** (FastAPI) — игры, промокоды, статусы.
3) **Worker** (отдельный процесс/контейнер) — отправка Telegram из outbox (надёжная доставка).
4) **PostgreSQL** — игры, промокоды, outbox, идемпотентность.

Почему нужен worker: Telegram — внешняя сеть. Нельзя держать пользовательский запрос “заложником” отправки; нужны ретраи, статус, отсутствие дублей.

---

## 4) Данные и модели (PostgreSQL)

### 4.1 Таблица `games`
Назначение: хранение состояния партии и её итогов.

Поля (рекомендуемый минимум):
- `id uuid pk`
- `created_at timestamptz`
- `updated_at timestamptz`
- `status` enum: `in_progress | player_won | computer_won | draw`
- `board text` длина 9, символы: `.` пусто, `X` игрок, `O` компьютер
- `next_turn` enum: `player | computer`
- `player_symbol char(1)` (по умолчанию `X`)
- `computer_symbol char(1)` (по умолчанию `O`)
- `move_count smallint`
- `promo_code_id uuid null` (FK)
- `finished_at timestamptz null`

Индексы:
- `status`
- `finished_at` (для отчётов)

### 4.2 Таблица `promo_codes`
- `id uuid pk`
- `code varchar(5) unique not null`
- `game_id uuid unique not null`
- `issued_at timestamptz not null`

Правило: **одна игра → максимум один промокод**.

### 4.3 Таблица `outbox_events`
Назначение: гарантировать доставку Telegram (минимум “at-least-once” + дедупликация).

Поля:
- `id uuid pk`
- `event_type text` (например `telegram_message`)
- `dedupe_key text unique` (например `telegram:game:{game_id}:result`)
- `payload jsonb` (chat_id, text, metadata)
- `status` enum: `pending | processing | sent | failed`
- `attempts int default 0`
- `next_retry_at timestamptz default now()`
- `locked_at timestamptz null`
- `locked_by text null`
- `created_at timestamptz`

Worker забирает пачку событий через `SELECT ... FOR UPDATE SKIP LOCKED` и обрабатывает.

### 4.4 Таблица `idempotency_keys`
Назначение: защита от повторов при ретраях/двойном клике.
- `key text pk`
- `request_hash text not null`
- `response jsonb not null`
- `created_at timestamptz not null`

---

## 5) Игровая логика (domain rules)

### 5.1 Поле и правила
- поле 3x3, индексация клеток 0..8 (слева направо, сверху вниз)
- игрок ходит своим символом (`X`), компьютер — (`O`)
- валидный ход:
  - игра `in_progress`
  - ходит тот, чей `next_turn`
  - клетка пустая

### 5.2 Определение результата
После каждого хода проверяем:
- победа игрока
- победа компьютера
- ничья (нет пустых клеток и победителя нет)
- иначе игра продолжается

### 5.3 AI компьютера
Требование к качеству: компьютер должен играть **не проигрывающе** (minimax).
- Если несколько лучших ходов — допускается выбирать случайно из лучших (с контролируемым seed в тестах) либо детерминированно (самый “малый индекс”).

---

## 6) Промокоды (правила выдачи)

### 6.1 Формат
- ровно **5 цифр**
- диапазон: `10000..99999` (без ведущих нулей)
- уникальность: enforced DB constraint `UNIQUE(code)`

### 6.2 Когда выдаём
- Только при `status = player_won`
- Генерация и запись промокода делаются **в транзакции** вместе с финализацией игры.

### 6.3 Антиабуз (обязательная продуктовая защита, т.к. промокоды = деньги)
Минимальный набор:
- Лимит выдачи промокодов:
  - 1 промокод на 24 часа на “анонимного пользователя” (cookie/session id) **и**
  - 1 промокод на 24 часа на IP (мягко, чтобы не ломать офисы)
- Технически:
  - генерируем `client_id` (uuid) на фронте и храним в localStorage/cookie
  - backend получает `client_id` в заголовке `X-Client-Id`
  - сохраняем `client_id` + `ip` в отдельной таблице `promo_issuance_limits` (или в `promo_codes.meta`)
- При превышении лимита: игра играться может, но промокод не выдаём, показываем сообщение “Промокоды на сегодня закончились” (это уже фронт; backend возвращает флаг).

Если антиабуз в проекте нежелателен — оставить как feature flag `PROMO_LIMITS_ENABLED=true`.

---

## 7) Telegram: бизнес-логика и надёжность

### 7.1 Что отправляем
- Победа: `Победа! Промокод выдан: 12345`
- Поражение: `Проигрыш`

### 7.2 Как обеспечиваем “ровно один раз”
- Событие кладём в `outbox_events` **в той же транзакции**, где меняем `games.status` на финальный.
- `dedupe_key` уникальный на игру и тип результата:
  - `telegram:game:{game_id}:player_won`
  - `telegram:game:{game_id}:computer_won`

### 7.3 Worker
- отдельный процесс, запускается в docker-compose как сервис `worker`
- цикл:
  - взять N событий `pending` с `next_retry_at <= now()` через `FOR UPDATE SKIP LOCKED`
  - пометить `processing`
  - отправить `sendMessage` в Telegram Bot API
  - если успех → `sent`
  - если ошибка → `failed`, увеличить `attempts`, выставить `next_retry_at` (экспоненциальная задержка до потолка, например 1m/5m/30m)
- Важно: worker не должен создавать дубли даже при рестарте (за счёт статусов + SKIP LOCKED + dedupe_key).

---

## 8) API спецификация (REST)

Базовый префикс: `/api/v1`

### 8.1 Создать игру
`POST /games`
Body:
```json
{
  "player_symbol": "X",
  "first_turn": "player"
}
```
Response 201:
```json
{
  "game_id": "uuid",
  "board": ".........",
  "status": "in_progress",
  "next_turn": "player",
  "player_symbol": "X",
  "computer_symbol": "O",
  "promo": { "available": true, "reason": null }
}
```
`promo.available` учитывает лимиты.

### 8.2 Сделать ход
`POST /games/{game_id}/moves`
Headers:
- `Idempotency-Key: <string>` (обязательный)
- `X-Client-Id: <uuid>` (обязательный для антиабуза)

Body:
```json
{ "cell": 0 }
```

Response 200:
```json
{
  "game_id": "uuid",
  "board": "X..O.....",
  "status": "in_progress",
  "next_turn": "player",
  "player_move": 0,
  "computer_move": 3,
  "promo_code": null,
  "promo": { "available": true, "reason": null }
}
```

Если победа игрока:
```json
{
  "status": "player_won",
  "promo_code": "48391",
  "promo": { "available": true, "reason": null }
}
```

Если промо лимит не позволяет выдачу:
```json
{
  "status": "player_won",
  "promo_code": null,
  "promo": { "available": false, "reason": "daily_limit" }
}
```

Ошибки:
- 404 game not found
- 409 не тот ход / игра завершена / клетка занята
- 422 неправильный `cell`

### 8.3 Получить состояние игры
`GET /games/{game_id}`

### 8.4 Health
- `GET /health` → 200 если процесс жив
- `GET /ready` → 200 если есть соединение с БД

---

## 9) Backend: транзакции и защита от race conditions

### 9.1 Правило обработки хода
Внутри одной транзакции:
1) `SELECT ... FOR UPDATE` строку игры
2) проверить валидность хода (status/next_turn/empty cell)
3) применить ход игрока
4) определить результат
5) если игра не завершена — вычислить и применить ход компьютера, снова определить результат
6) если финал:
   - при победе игрока и promo available → создать promo_code (с UNIQUE + retry при коллизии)
   - создать outbox_event для Telegram с уникальным dedupe_key
7) записать изменения, commit
8) API возвращает финальный board/status/promo_code (если выдан)

Никаких внешних HTTP-вызовов внутри транзакции.

### 9.2 Идемпотентность
`Idempotency-Key` обязателен на `POST /moves`. Повтор с тем же ключом:
- если `request_hash` совпадает → вернуть сохранённый `response`
- если отличается → 409 (или 422) “Idempotency key reuse with different payload”

---

## 10) Frontend: экраны и дизайн-система

### 10.1 Технология (рекомендуемая)
- Next.js или Vite+React (на выбор исполнителя), TypeScript желателен.
- API общение: fetch/axios, обработка 409/422.

### 10.2 Экраны/состояния
- Loading
- Start (объяснение + CTA)
- Playing (поле 3x3, индикатор хода)
- Win (промокод + copy + play again)
- Lose (play again)
- Draw (play again)
- Error state (если backend недоступен)

### 10.3 UI-детали
- Подсветка победной линии
- Блокировка ввода во время “хода компьютера” (чтобы не спамили)
- Храним `game_id` в localStorage, чтобы при обновлении страницы можно восстановить `GET /games/{id}` (если status in_progress — продолжаем, иначе показываем финал)

---

## 11) Инфраструктура и деплой (обязательно для “рабочей ссылки”)

### 11.1 Контейнеризация
- `Dockerfile` для backend
- `docker-compose.yml`:
  - `api`
  - `worker`
  - `db`

### 11.2 CI
GitHub Actions (минимум):
- `ruff check` + `ruff format --check`
- `mypy --strict`
- `pytest` + coverage gate ≥ 75%

### 11.3 Production deploy (варианты)
Допускается любой хостинг, но должен дать публичную ссылку:
- Backend+Worker: Render/Fly.io/Railway (Docker)
- DB: managed Postgres (или тот же Render/Railway)
- Frontend: Vercel/Netlify/Cloudflare Pages (или тоже Render)

README должен содержать:
- переменные окружения
- команды локального запуска
- команды миграций
- ссылку на прод

---

## 12) Acceptance Criteria (чеклист)
- [ ] Игра работает на мобильных и десктопе
- [ ] Компьютер играет без проигрышей (minimax)
- [ ] При победе игрока промокод генерируется, отображается, копируется
- [ ] Telegram получает корректные сообщения
- [ ] Сообщение в Telegram не дублируется при ретраях/двойных кликах
- [ ] При проигрыше Telegram получает “Проигрыш”
- [ ] API защищён от race conditions (FOR UPDATE + идемпотентность)
- [ ] Тесты ≥ 75% coverage
- [ ] ruff + mypy strict зелёные
- [ ] Docker compose поднимает всё локально
- [ ] Есть публичная рабочая ссылка