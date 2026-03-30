"""
API tests for /meetings — CRUD, audio upload, transcript, correct, summarize.
No external services: DB is in-memory SQLite, storage and Celery are mocked.
"""
import uuid


# ── Meetings CRUD ─────────────────────────────────────────────────────────────

def test_create_meeting_minimal(api_client):
    resp = api_client.post("/meetings", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["language"] == "zh"
    assert "會議" in data["title"]


def test_create_meeting_all_fields(api_client):
    resp = api_client.post("/meetings", json={
        "title": "Sprint Review",
        "date": "2026-03-20",
        "language": "en",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Sprint Review"
    assert data["date"] == "2026-03-20"
    assert data["language"] == "en"


def test_create_meeting_invalid_date(api_client):
    resp = api_client.post("/meetings", json={"date": "not-a-date"})
    assert resp.status_code == 422


def test_list_meetings_empty(api_client):
    assert api_client.get("/meetings").json() == []


def test_list_meetings(api_client):
    api_client.post("/meetings", json={"title": "A"})
    api_client.post("/meetings", json={"title": "B"})
    meetings = api_client.get("/meetings").json()
    assert len(meetings) == 2


def test_get_meeting(api_client):
    mid = api_client.post("/meetings", json={"title": "My Meeting"}).json()["id"]
    resp = api_client.get(f"/meetings/{mid}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "My Meeting"


def test_get_meeting_not_found(api_client):
    assert api_client.get(f"/meetings/{uuid.uuid4()}").status_code == 404


def test_update_meeting_title(api_client):
    mid = api_client.post("/meetings", json={"title": "Old"}).json()["id"]
    resp = api_client.put(f"/meetings/{mid}", json={"title": "New"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"


def test_update_meeting_not_found(api_client):
    assert api_client.put(f"/meetings/{uuid.uuid4()}", json={"title": "X"}).status_code == 404


def test_delete_meeting(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    assert api_client.delete(f"/meetings/{mid}").status_code == 204
    assert api_client.get(f"/meetings/{mid}").status_code == 404


def test_delete_meeting_not_found(api_client):
    assert api_client.delete(f"/meetings/{uuid.uuid4()}").status_code == 404


def test_delete_meeting_removes_from_list(api_client):
    mid = api_client.post("/meetings", json={"title": "Temp"}).json()["id"]
    api_client.delete(f"/meetings/{mid}")
    meetings = api_client.get("/meetings").json()
    assert all(m["id"] != mid for m in meetings)


# ── Audio upload ──────────────────────────────────────────────────────────────

def test_upload_audio_returns_task_and_transcript(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"fake audio", "audio/mpeg")},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "task_id" in data
    assert "transcript_id" in data
    assert data["status"] == "pending"


def test_upload_audio_queues_celery_task(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"fake audio", "audio/mpeg")},
    )
    api_client._celery.send_task.assert_called_once()
    task_name = api_client._celery.send_task.call_args[0][0]
    assert task_name == "services.task_worker.tasks.stt.run_stt"


def test_upload_audio_meeting_not_found(api_client):
    resp = api_client.post(
        f"/meetings/{uuid.uuid4()}/audio",
        files={"audio": ("test.mp3", b"x", "audio/mpeg")},
    )
    assert resp.status_code == 404


def test_upload_audio_stores_file(api_client, mock_storage):
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio content", "audio/mpeg")},
    )
    keys = list(mock_storage._data.keys())
    assert any("audio" in k for k in keys)


# ── Transcript ────────────────────────────────────────────────────────────────

def test_get_transcript_not_found(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    assert api_client.get(f"/meetings/{mid}/transcript").status_code == 404


def test_get_transcript_after_upload(api_client):
    """Transcript row exists after audio upload even before worker completes."""
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    )
    resp = api_client.get(f"/meetings/{mid}/transcript")
    assert resp.status_code == 200
    data = resp.json()
    assert data["meeting_id"] == mid
    assert data["raw"] is None       # worker hasn't run yet
    assert data["corrected"] is None


def test_update_transcript(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    )
    resp = api_client.put(
        f"/meetings/{mid}/transcript",
        json={"corrected": "手動修正的逐字稿"},
    )
    assert resp.status_code == 200
    assert resp.json()["corrected"] == "手動修正的逐字稿"


def test_update_transcript_not_found(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.put(f"/meetings/{mid}/transcript", json={"corrected": "x"})
    assert resp.status_code == 404


# ── Correction ────────────────────────────────────────────────────────────────

def test_correct_no_transcript(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    assert api_client.post(f"/meetings/{mid}/correct", json={}).status_code == 404


def test_correct_no_raw_ref(api_client):
    """Transcript exists (audio uploaded) but worker hasn't written raw_ref yet."""
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/audio",
        files={"audio": ("test.mp3", b"audio", "audio/mpeg")},
    )
    # raw_ref is None until STT worker completes → 404
    assert api_client.post(f"/meetings/{mid}/correct", json={}).status_code == 404


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summarize_no_transcript(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    assert api_client.post(f"/meetings/{mid}/summarize", json={}).status_code == 404


def test_get_summary_not_found(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    assert api_client.get(f"/meetings/{mid}/summary").status_code == 404


def test_list_summaries_empty(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.get(f"/meetings/{mid}/summaries")
    assert resp.status_code == 200
    assert resp.json() == []


def test_delete_summary_not_found(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.delete(f"/meetings/{mid}/summaries/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Direct transcript input ───────────────────────────────────────────────────

def test_create_transcript_from_text(api_client, mock_storage):
    mid = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.post(
        f"/meetings/{mid}/transcript",
        json={"text": "這是手動輸入的逐字稿", "language": "zh"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["raw"] == "這是手動輸入的逐字稿"
    assert data["corrected"] == "這是手動輸入的逐字稿"
    assert data["language"] == "zh"
    assert data["duration_seconds"] is None


def test_create_transcript_stores_to_storage(api_client, mock_storage):
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/transcript",
        json={"text": "test content", "language": "zh"},
    )
    keys = list(mock_storage._data.keys())
    assert any("raw.txt" in k for k in keys)
    assert any("corrected.txt" in k for k in keys)


def test_create_transcript_meeting_not_found(api_client):
    resp = api_client.post(
        f"/meetings/{uuid.uuid4()}/transcript",
        json={"text": "test", "language": "zh"},
    )
    assert resp.status_code == 404


def test_create_transcript_then_get(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/transcript",
        json={"text": "直接輸入的逐字稿內容", "language": "en"},
    )
    resp = api_client.get(f"/meetings/{mid}/transcript")
    assert resp.status_code == 200
    data = resp.json()
    assert data["raw"] == "直接輸入的逐字稿內容"
    assert data["corrected"] == "直接輸入的逐字稿內容"
    assert data["language"] == "en"


def test_create_transcript_allows_summarize(api_client):
    """Direct transcript input sets corrected_ref so summarize can proceed."""
    mid = api_client.post("/meetings", json={}).json()["id"]
    api_client.post(
        f"/meetings/{mid}/transcript",
        json={"text": "逐字稿", "language": "zh"},
    )
    resp = api_client.post(f"/meetings/{mid}/summarize", json={})
    assert resp.status_code == 202


# ── Health / Info ──────────────────────────────────────────────────────────────

def test_health_endpoint(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_info_endpoint(api_client):
    resp = api_client.get("/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "stt_model" in data
    assert "stt_service_url" in data
    assert "llm_model" in data
    assert "llm_base_url" in data
