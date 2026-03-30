"""
API tests for /documents — aggregation list/get, generate.
"""
import uuid


def test_list_aggregations_empty(api_client):
    resp = api_client.get("/documents/aggregations")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_aggregation_not_found(api_client):
    assert api_client.get(f"/documents/aggregations/{uuid.uuid4()}").status_code == 404


def test_start_aggregation_requires_at_least_two(api_client):
    mid = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.post("/documents/aggregate", json={"meeting_ids": [mid]})
    assert resp.status_code == 422


def test_start_aggregation_no_summaries(api_client):
    m1 = api_client.post("/meetings", json={}).json()["id"]
    m2 = api_client.post("/meetings", json={}).json()["id"]
    resp = api_client.post("/documents/aggregate", json={"meeting_ids": [m1, m2]})
    assert resp.status_code == 404  # no summaries found for those meetings


def test_generate_document_not_found(api_client):
    resp = api_client.post(f"/documents/generate/{uuid.uuid4()}")
    assert resp.status_code == 404
