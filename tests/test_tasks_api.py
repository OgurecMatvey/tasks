from tests.helpers import auth_headers, make_task


async def test_crud_flow(client):
    headers = await auth_headers(client)
    created = await make_task(client, headers, title="  Write report  ", description="Q3", priority=3)
    assert created["title"] == "Write report"
    assert created["status"] == "todo" and created["priority"] == 3

    fetched = await client.get(f"/tasks/{created['id']}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["description"] == "Q3"

    patched = await client.patch(
        f"/tasks/{created['id']}", json={"status": "done", "due_date": "2026-12-31"}, headers=headers
    )
    assert patched.status_code == 200
    body = patched.json()
    assert (body["status"], body["due_date"], body["title"]) == ("done", "2026-12-31", "Write report")
    assert body["updated_at"] >= created["updated_at"]

    assert (await client.delete(f"/tasks/{created['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"/tasks/{created['id']}", headers=headers)).status_code == 404
    assert (await client.delete(f"/tasks/{created['id']}", headers=headers)).status_code == 404


async def test_patch_can_clear_optional_fields_but_not_required_ones(client):
    headers = await auth_headers(client)
    task = await make_task(client, headers, description="text", due_date="2026-12-31")
    url = f"/tasks/{task['id']}"

    cleared = await client.patch(url, json={"description": None, "due_date": None}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None and cleared.json()["due_date"] is None

    for payload in ({"title": None}, {"status": None}, {"priority": None}):
        response = await client.patch(url, json=payload, headers=headers)
        assert response.status_code == 422, payload


async def test_validation(client):
    headers = await auth_headers(client)
    bad_payloads = [
        {},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "ok", "status": "finished"},
        {"title": "ok", "priority": 5},
        {"title": "ok", "due_date": "not-a-date"},
    ]
    for payload in bad_payloads:
        response = await client.post("/tasks", json=payload, headers=headers)
        assert response.status_code == 422, payload


async def test_users_see_only_their_own_tasks(client):
    alice = await auth_headers(client, "alice@example.com")
    bob = await auth_headers(client, "bob@example.com")
    task = await make_task(client, alice, title="Alice secret")
    url = f"/tasks/{task['id']}"

    assert (await client.get(url, headers=bob)).status_code == 404
    assert (await client.patch(url, json={"title": "hacked"}, headers=bob)).status_code == 404
    assert (await client.delete(url, headers=bob)).status_code == 404

    bobs_list = (await client.get("/tasks", headers=bob)).json()
    assert bobs_list["items"] == [] and bobs_list["total"] == 0

    # после попыток Боба задача Алисы не изменилась
    assert (await client.get(url, headers=alice)).json()["title"] == "Alice secret"


async def test_filters(client):
    headers = await auth_headers(client)
    await make_task(client, headers, title="Buy milk", status="todo", priority=1)
    await make_task(client, headers, title="Write report", status="in_progress", priority=3)
    await make_task(client, headers, title="Buy tickets", status="done", priority=2, due_date="2026-01-10")
    await make_task(client, headers, title="Reach 100% coverage", status="todo", priority=3, due_date="2026-06-01")

    async def titles(query: str) -> list[str]:
        response = await client.get(f"/tasks?{query}", headers=headers)
        assert response.status_code == 200, response.text
        return sorted(item["title"] for item in response.json()["items"])

    assert await titles("status=todo") == ["Buy milk", "Reach 100% coverage"]
    assert await titles("priority=3") == ["Reach 100% coverage", "Write report"]
    assert await titles("status=todo&priority=3") == ["Reach 100% coverage"]
    assert await titles("q=buy") == ["Buy milk", "Buy tickets"]  # без учёта регистра
    assert await titles("q=100%25") == ["Reach 100% coverage"]  # % ищется буквально, а не как маска
    assert await titles("q=%25") == ["Reach 100% coverage"]
    assert await titles("due_before=2026-03-01") == ["Buy tickets"]
    assert await titles("status=done&q=report") == []

    assert (await client.get("/tasks?status=finished", headers=headers)).status_code == 422
    assert (await client.get("/tasks?priority=9", headers=headers)).status_code == 422


async def test_pagination(client):
    headers = await auth_headers(client)
    created = [await make_task(client, headers, title=f"t{i}") for i in range(5)]
    ids_newest_first = [t["id"] for t in reversed(created)]

    first = (await client.get("/tasks?limit=2&offset=0", headers=headers)).json()
    second = (await client.get("/tasks?limit=2&offset=2", headers=headers)).json()
    last = (await client.get("/tasks?limit=2&offset=4", headers=headers)).json()
    beyond = (await client.get("/tasks?limit=2&offset=10", headers=headers)).json()

    assert [t["id"] for t in first["items"]] == ids_newest_first[0:2]
    assert [t["id"] for t in second["items"]] == ids_newest_first[2:4]  # страницы не перекрываются
    assert [t["id"] for t in last["items"]] == ids_newest_first[4:5]
    assert beyond["items"] == []
    for page in (first, second, last, beyond):
        assert page["total"] == 5  # total не зависит от limit и offset
    assert (first["limit"], first["offset"]) == (2, 0)

    assert (await client.get("/tasks?limit=0", headers=headers)).status_code == 422
    assert (await client.get("/tasks?limit=101", headers=headers)).status_code == 422
    assert (await client.get("/tasks?offset=-1", headers=headers)).status_code == 422


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}
