# Tasks API

REST API для списка задач: регистрация и вход по JWT, пароли хранятся как bcrypt-хеши.
Каждый пользователь видит только свои задачи. CRUD, фильтры, пагинация.

**Стек:** FastAPI, PostgreSQL, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic, JWT (PyJWT), bcrypt, pytest, Docker Compose.

## Запуск

```bash
copy .env.example .env        # Linux/macOS: cp .env.example .env
# в .env замени SECRET_KEY на длинную случайную строку
docker compose up --build     # db, migrate (миграции), api
```

Swagger: http://localhost:8002/docs (кнопка **Authorize** работает с `/auth/login`).

### Без Docker

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db       # PostgreSQL на localhost:5434
alembic upgrade head
uvicorn app.main:app --reload
```

## Быстрая проверка

```bash
curl -X POST localhost:8002/auth/register -H 'content-type: application/json' \
     -d '{"email":"me@example.com","password":"supersecret1"}'

TOKEN=$(curl -s -X POST localhost:8002/auth/login \
     -d 'username=me@example.com&password=supersecret1' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -X POST localhost:8002/tasks -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
     -d '{"title":"Write report","priority":3,"due_date":"2026-12-31"}'

curl "localhost:8002/tasks?status=todo&q=report&limit=10" -H "authorization: Bearer $TOKEN"
```

В Swagger проще: `POST /auth/register`, затем кнопка Authorize (username = email), затем любые эндпоинты.

## Эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| POST | `/auth/register` | регистрация |
| POST | `/auth/login` | вход (форма: username = email, password), возвращает JWT |
| GET | `/auth/me` | текущий пользователь |
| POST | `/tasks` | создать задачу |
| GET | `/tasks` | список своих задач: фильтры `status`, `priority`, `q` (поиск по заголовку), `due_before`; пагинация `limit` (1–100, по умолчанию 20) и `offset`; ответ содержит `total` |
| GET/PATCH/DELETE | `/tasks/{id}` | одна задача |
| GET | `/health` | проверка живости и БД |

Поля задачи: `title`, `description`, `status` (`todo`, `in_progress`, `done`), `priority` (1–3), `due_date`.

## Структура

```
app/
  main.py          приложение, /health, проверка SECRET_KEY в production
  config.py        настройки из .env
  database.py      async engine / session
  models.py        User, Task
  auth_schemas.py  схемы пользователя и токена
  schemas.py       схемы задач и валидация
  security.py      bcrypt + JWT
  deps.py          get_current_user
  utils.py         escape_like (экранирование поиска)
  routers/
    auth.py        регистрация, вход, /auth/me
    tasks.py       CRUD, фильтры, пагинация
alembic/           миграции
tests/             pytest
```

## Принятые решения (для собеседования)

**Изоляция данных.** Во всех запросах к задачам условие `user_id = текущий пользователь` есть всегда,
поэтому чужие строки физически не попадают в выборку. Чужая и несуществующая задача отвечают одинаково
(404), чтобы нельзя было перебором узнать чужие id.

**Пароли.** Хранится только bcrypt-хеш (медленный алгоритм с солью, пароль восстановить нельзя).
Хеширование вынесено в отдельный поток, чтобы не блокировать event loop. Лимит пароля 72 байта: так
устроен bcrypt. Ответ при неверном пароле и при неизвестном email одинаков, а пароль проверяется всегда
(против фиктивного хеша), поэтому по ответу и времени нельзя узнать, зарегистрирован ли email.

**JWT.** В токене id пользователя (`sub`) и срок жизни (`exp`), подпись HS256 ключом `SECRET_KEY`.
Сервер не хранит сессии. Минус: токен нельзя отозвать до истечения. В режиме
`ENVIRONMENT=production` приложение не стартует со слабым ключом.

**Регистрация без предварительного SELECT.** Уникальность email гарантирует индекс. Проверка «есть ли
такой email» перед вставкой дала бы гонку: два параллельных запроса оба прошли бы проверку.

**PATCH отличает «не передано» от «null».** `model_dump(exclude_unset=True)` берёт только переданные поля.
`description` и `due_date` можно очистить, передав `null`; для `title`, `status`, `priority` null даёт 422.

**Пагинация.** `limit`/`offset` и `total` (число задач под фильтр, не зависящее от страницы). Порядок
`id DESC` стабилен, поэтому страницы не перекрываются. Минус offset-пагинации: на больших смещениях она
медленнее курсорной.

**Поиск по заголовку** через `ILIKE`; символы `%` и `_` экранируются, поэтому поиск «100%» ищет именно «100%».

**Индекс** `(user_id, status)` под главный запрос «мои задачи по статусу».

## Тесты

```bash
pip install -r requirements-dev.txt
docker compose up -d db        # тестам нужен PostgreSQL; БД tasks_test создаётся автоматически
pytest
ruff check .
```

Тесты идут на настоящем PostgreSQL, миграции накатываются с нуля в начале сессии, отдельный тест
сравнивает модели с миграциями. Схемы и вспомогательные функции (`test_schemas`, `test_utils`)
работают без БД.

## Ограничения

- Нет refresh-токенов и отзыва токена (logout не инвалидирует JWT).
- Нет ограничения частоты запросов на вход и регистрацию (защиты от подбора пароля).
- Нет подтверждения email и восстановления пароля.
