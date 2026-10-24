"""End-to-end API integration tests for CleanCheck."""

import io
from pathlib import Path
import pytest
from app import app
from config import SAMPLES_DIR


import uuid
from backend.db import get_db_connection, init_db


@pytest.fixture
def client():
    app.config["TESTING"] = True
    init_db()
    # Clear scans table so each test run is fresh and not blocked by duplicate hash
    conn = get_db_connection()
    conn.execute("DELETE FROM scans")
    conn.commit()
    conn.close()

    with app.test_client() as client:
        yield client


def test_api_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "online"
    assert data["service"] == "CleanCheck Engine"
    assert data["provider_mode"] == "demo"


def test_api_ledger_get_and_post(client):
    # 1. GET ledger
    get_resp = client.get("/api/ledger")
    assert get_resp.status_code == 200
    get_data = get_resp.get_json()
    assert get_data["success"] is True
    assert len(get_data["records"]) > 0

    # 2. POST custom transaction with unique UTR
    unique_utr = f"49{str(uuid.uuid4().int)[:10]}"
    post_payload = {
        "txn_id": unique_utr,
        "amount": 999.00,
        "payer_name": "Test Payer",
        "notes": "Pytest API Test",
    }
    post_resp = client.post("/api/ledger", json=post_payload)
    assert post_resp.status_code == 200
    post_data = post_resp.get_json()
    assert post_data["success"] is True


def test_api_quick_verify(client):
    quick_utr = f"43{str(uuid.uuid4().int)[:10]}"
    resp = client.post(
        "/api/quick-verify",
        json={"txn_id": quick_utr, "amount": 500.0, "payer_name": "Demo User"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_api_samples(client):
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["samples"]) == 4


def test_api_analyze_missing_file(client):
    resp = client.post("/api/analyze", data={})
    assert resp.status_code == 400


def test_api_analyze_genuine_sample(client):
    sample_path = SAMPLES_DIR / "sample_genuine.png"
    assert sample_path.exists(), "Sample genuine file should exist"

    with open(sample_path, "rb") as f:
        file_bytes = io.BytesIO(f.read())

    resp = client.post(
        "/api/analyze",
        data={"image": (file_bytes, "sample_genuine.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "VERIFIED"
    assert data["extracted"]["amount"] == 750.0
    assert data["extracted"]["txn_id"] == "428901928374"
    assert data["record_match"]["found"] is True
    assert data["record_match"]["matched"] is True


def test_api_analyze_tampered_sample(client):
    sample_path = SAMPLES_DIR / "sample_tampered.png"
    assert sample_path.exists()

    with open(sample_path, "rb") as f:
        file_bytes = io.BytesIO(f.read())

    resp = client.post(
        "/api/analyze",
        data={"image": (file_bytes, "sample_tampered.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "SUSPICIOUS"
    assert len(data["verdict_reasons"]) > 0


def test_api_analyze_non_payment_sample(client):
    sample_path = SAMPLES_DIR / "sample_non_payment.png"
    assert sample_path.exists()

    with open(sample_path, "rb") as f:
        file_bytes = io.BytesIO(f.read())

    resp = client.post(
        "/api/analyze",
        data={"image": (file_bytes, "sample_non_payment.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "UNVERIFIED"
