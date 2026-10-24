"""Unit tests for perceptual hash duplicate and collision detection."""

import uuid
from pathlib import Path
from PIL import Image
import imagehash
import pytest
from backend.db import init_db, log_scan_result
from backend.forensics import check_duplicates
from config import SAMPLES_DIR


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_unique_image_duplicate_check(tmp_path):
    # Create brand new unique image
    test_img = tmp_path / "unique_test.png"
    img = Image.new("RGB", (100, 100), color=(120, 200, 240))
    img.save(test_img)

    res, phash_str = check_duplicates(test_img, current_txn_id="499999999999", current_amount=100.0)
    assert res["is_duplicate"] is False
    assert res["flag"] is False
    assert len(phash_str) > 0


def test_duplicate_reupload_detection(tmp_path):
    # Create base image
    base_img_path = tmp_path / "base_img.png"
    img = Image.new("RGB", (120, 120), color=(80, 180, 90))
    img.save(base_img_path)
    phash_val = str(imagehash.phash(img))

    # Log initial scan into DB
    log_scan_result({
        "scan_id": str(uuid.uuid4()),
        "phash": phash_val,
        "extracted_txn_id": "411122223333",
        "extracted_amount": 500.0,
        "risk_score": 10.0,
        "verdict": "VERIFIED",
    })

    # Now test re-submitting an identical copy
    copy_img_path = tmp_path / "copy_img.png"
    img.save(copy_img_path)

    res, _ = check_duplicates(copy_img_path, current_txn_id="411122223333", current_amount=500.0)
    assert res["is_duplicate"] is True
    assert res["flag"] is True
    assert "Duplicate screenshot detected" in res["detail"]


def test_txn_id_amount_collision(tmp_path):
    from PIL import ImageDraw
    # Log a previous scan with UTR 422233334444 and amount 200.0
    first_img_path = tmp_path / "first.png"
    img1 = Image.new("RGB", (100, 100), color=(255, 255, 255))
    d1 = ImageDraw.Draw(img1)
    d1.rectangle([(0, 0), (50, 100)], fill=(0, 0, 0))
    img1.save(first_img_path)

    log_scan_result({
        "scan_id": str(uuid.uuid4()),
        "phash": str(imagehash.phash(img1)),
        "extracted_txn_id": "422233334444",
        "extracted_amount": 200.0,
        "risk_score": 10.0,
        "verdict": "VERIFIED",
    })

    # Second image with distinct pattern (different phash) but same UTR with amount 2000.0
    second_img_path = tmp_path / "second.png"
    img2 = Image.new("RGB", (100, 100), color=(255, 255, 255))
    d2 = ImageDraw.Draw(img2)
    d2.ellipse([(10, 10), (90, 90)], fill=(200, 50, 50))
    img2.save(second_img_path)

    res, _ = check_duplicates(second_img_path, current_txn_id="422233334444", current_amount=2000.0)
    assert res["is_duplicate"] is True
    assert res["flag"] is True
    assert "Transaction ID collision" in res["detail"]
