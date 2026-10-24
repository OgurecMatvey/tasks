async def auth_headers(client, email: str = "user@example.com", password: str = "supersecret1") -> dict:
    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_task(client, headers: dict, **payload) -> dict:
    payload.setdefault("title", "Task")
    response = await client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
