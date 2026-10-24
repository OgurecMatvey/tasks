from tests.helpers import auth_headers


async def test_register_login_me(client):
    headers = await auth_headers(client, "Me@Example.com")
    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"  # email приводится к нижнему регистру
    assert "password" not in body and "hashed_password" not in body


async def test_password_is_stored_as_bcrypt_hash(client, session_factory):
    from sqlalchemy import select

    from app.models import User

    await auth_headers(client, "hash@example.com", "supersecret1")
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.email == "hash@example.com"))).scalar_one()
    assert user.hashed_password != "supersecret1"
    assert user.hashed_password.startswith("$2")  # префикс bcrypt


async def test_duplicate_email_is_conflict_case_insensitive(client):
    await auth_headers(client, "dup@example.com")
    response = await client.post("/auth/register", json={"email": "DUP@example.com", "password": "supersecret1"})
    assert response.status_code == 409


async def test_weak_or_oversized_passwords_are_rejected(client):
    for password in ("short", "я" * 40):  # 40 кириллических символов = 80 байт > лимита bcrypt
        response = await client.post("/auth/register", json={"email": "p@example.com", "password": password})
        assert response.status_code == 422, password


async def test_login_errors_do_not_reveal_whether_email_exists(client):
    await auth_headers(client, "known@example.com")
    wrong = await client.post("/auth/login", data={"username": "known@example.com", "password": "nope-nope-nope"})
    unknown = await client.post("/auth/login", data={"username": "ghost@example.com", "password": "supersecret1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_protected_routes_require_valid_token(client):
    assert (await client.get("/auth/me")).status_code == 401
    bad = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401
    assert (await client.get("/tasks")).status_code == 401
    assert (await client.post("/tasks", json={"title": "x"})).status_code == 401
