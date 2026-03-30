"""
API tests for /tasks — list, get, cancel.
"""
import uuid


def test_list_tasks_empty(api_client):
    assert api_client.get("/tasks").json() == []


def test_get_task_not_found(api_client):
    assert api_client.get(f"/tasks/{uuid.uuid4()}").status_code == 404


def test_cancel_task_not_found(api_client):
    assert api_client.post(f"/tasks/{uuid.uuid4()}/cancel").status_code == 404


def test_task_created_after_audio_upload(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    )
    tasks = api_client.get("/tasks").json()
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "stt"
    assert tasks[0]["status"] == "pending"


def test_filter_tasks_by_meeting(api_client):
    m1 = api_client.post("/meetings", json={"title": "A"}).json()["id"]
    m2 = api_client.post("/meetings", json={"title": "B"}).json()["id"]
    api_client.post(f"/meetings/{m1}/audio", files={"audio": ("a.mp3", b"x", "audio/mpeg")})
    api_client.post(f"/meetings/{m2}/audio", files={"audio": ("b.mp3", b"x", "audio/mpeg")})

    tasks_m1 = api_client.get("/tasks", params={"meeting_id": m1}).json()
    assert len(tasks_m1) == 1
    assert tasks_m1[0]["meeting_id"] == m1


def test_get_task_by_id(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    task_id = api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    ).json()["task_id"]

    resp = api_client.get(f"/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == task_id
    assert resp.json()["task_type"] == "stt"


def test_cancel_pending_task(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    task_id = api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    ).json()["task_id"]

    resp = api_client.post(f"/tasks/{task_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_already_terminal_task(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    task_id = api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    ).json()["task_id"]

    api_client.post(f"/tasks/{task_id}/cancel")  # first cancel → cancelled
    resp = api_client.post(f"/tasks/{task_id}/cancel")  # second → conflict
    assert resp.status_code == 409


def test_cancel_calls_celery_revoke(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    task_id = api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    ).json()["task_id"]

    api_client.post(f"/tasks/{task_id}/cancel")
    api_client._celery_tasks.control.revoke.assert_called_once()
