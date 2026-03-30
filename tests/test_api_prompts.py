"""
API tests for /prompts — CRUD for custom prompts, builtin read-only guard.
"""
import uuid


def test_list_prompts_includes_all_builtins(api_client):
    resp = api_client.get("/prompts")
    assert resp.status_code == 200
    scenes = {p["scene"] for p in resp.json()}
    for expected in ("general", "weekly_standup", "project_review", "client_interview"):
        assert expected in scenes


def test_list_prompts_builtins_have_no_id(api_client):
    builtins = [p for p in api_client.get("/prompts").json() if p["is_builtin"]]
    assert len(builtins) >= 4
    assert all(p["id"] is None for p in builtins)


def test_create_custom_prompt(api_client):
    resp = api_client.post("/prompts", json={
        "name": "My Prompt",
        "system_prompt": "You are a helper.",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Prompt"
    assert data["scene"] == "custom"
    assert data["is_builtin"] is False
    assert data["id"] is not None


def test_create_prompt_missing_fields(api_client):
    resp = api_client.post("/prompts", json={"name": "No body"})
    assert resp.status_code == 422


def test_get_custom_prompt(api_client):
    pid = api_client.post("/prompts", json={
        "name": "Test", "system_prompt": "Hello"
    }).json()["id"]
    resp = api_client.get(f"/prompts/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test"


def test_get_prompt_not_found(api_client):
    assert api_client.get(f"/prompts/{uuid.uuid4()}").status_code == 404


def test_update_custom_prompt(api_client):
    pid = api_client.post("/prompts", json={
        "name": "Old", "system_prompt": "Old text"
    }).json()["id"]
    resp = api_client.put(f"/prompts/{pid}", json={"name": "New", "system_prompt": "New text"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    assert resp.json()["system_prompt"] == "New text"


def test_update_prompt_not_found(api_client):
    assert api_client.put(f"/prompts/{uuid.uuid4()}", json={"name": "X"}).status_code == 404


def test_delete_custom_prompt(api_client):
    pid = api_client.post("/prompts", json={
        "name": "Delete Me", "system_prompt": "..."
    }).json()["id"]
    assert api_client.delete(f"/prompts/{pid}").status_code == 204
    assert api_client.get(f"/prompts/{pid}").status_code == 404


def test_delete_prompt_not_found(api_client):
    assert api_client.delete(f"/prompts/{uuid.uuid4()}").status_code == 404


def test_list_prompts_includes_custom(api_client):
    api_client.post("/prompts", json={"name": "Custom1", "system_prompt": "P1"})
    api_client.post("/prompts", json={"name": "Custom2", "system_prompt": "P2"})
    custom = [p for p in api_client.get("/prompts").json() if not p["is_builtin"]]
    assert len(custom) == 2
