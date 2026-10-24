"""Database and Persistence Layer for CleanCheck

Handles SQLite database initialization, ledger storage for trusted records,
scan history persistence, and perceptual hash tracking for duplicate detection.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Add root directory to sys.path if not present
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with dictionary-like row access."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force_reseed: bool = False) -> None:
    """Initializes tables and seeds initial realistic demo ledger transactions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Mock Ledger (Simulated bank/provider ledger)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            payer_name TEXT,
            payer_vpa TEXT,
            payee_vpa TEXT,
            timestamp TEXT NOT NULL,
            bank_ref TEXT,
            status TEXT DEFAULT 'SUCCESS',
            app_source TEXT DEFAULT 'UPI',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Table 2: Scan History & Duplicate Hashes
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id TEXT UNIQUE NOT NULL,
            phash TEXT,
            extracted_txn_id TEXT,
            extracted_amount REAL,
            extracted_date TEXT,
            extracted_sender TEXT,
            extracted_receiver TEXT,
            extracted_app TEXT,
            risk_score REAL,
            verdict TEXT NOT NULL,
            verdict_reasons TEXT,
            checks_json TEXT,
            match_json TEXT,
            ela_image_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_txn ON ledger(txn_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_phash ON scans(phash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_txn ON scans(extracted_txn_id)")

    conn.commit()

    # Check if ledger needs seeding
    cursor.execute("SELECT COUNT(*) as count FROM ledger")
    row_count = cursor.fetchone()["count"]

    if row_count == 0 or force_reseed:
        if force_reseed:
            cursor.execute("DELETE FROM ledger")
        _seed_demo_ledger(cursor)
        conn.commit()

    conn.close()


def _seed_demo_ledger(cursor: sqlite3.Cursor) -> None:
    """Seeds ~30 realistic mock transactions across common Indian payment apps."""
    now = datetime.now()

    # Formatted relative dates
    d0 = now.strftime("%Y-%m-%d %H:%M:%S")
    d1 = (now - timedelta(hours=2, minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    d2 = (now - timedelta(hours=5, minutes=40)).strftime("%Y-%m-%d %H:%M:%S")
    d3 = (now - timedelta(days=1, hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    d4 = (now - timedelta(days=1, hours=4)).strftime("%Y-%m-%d %H:%M:%S")
    d5 = (now - timedelta(days=2, hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    d6 = (now - timedelta(days=3, hours=6)).strftime("%Y-%m-%d %H:%M:%S")

    demo_records = [
        # Prime test sample record (Matches Sample A)
        ("428901928374", 750.00, "Rohan Sharma", "rohan.sharma@okaxis", "shopeasy@hdfcbank", d0, "HDFC001289", "SUCCESS", "Google Pay", "Groceries payment"),
        ("429810293847", 1250.00, "Ananya Iyer", "ananya.iyer@okhdfcbank", "shopeasy@hdfcbank", d1, "HDFC009210", "SUCCESS", "Google Pay", "Electronics accessory"),
        ("420193847562", 340.00, "Vikas Gupta", "vikasgupta@paytm", "shopeasy@hdfcbank", d1, "PAYTM49201", "SUCCESS", "Paytm", "Stationery"),
        ("418273645192", 2100.00, "Pooja Mehta", "pooja.mehta@ybl", "shopeasy@hdfcbank", d2, "YESB002819", "SUCCESS", "PhonePe", "Garments"),
        ("417382910482", 85.00, "Arjun Nair", "arjunnair@ibl", "shopeasy@hdfcbank", d2, "ICIC003829", "SUCCESS", "PhonePe", "Dairy items"),
        ("416273849102", 500.00, "Sunita Rao", "sunita.rao@axisbank", "shopeasy@hdfcbank", d3, "UTIB001928", "SUCCESS", "BHIM", "Medicine"),
        ("415382910293", 1499.00, "Karan Malhotra", "karan.malhotra@okicici", "shopeasy@hdfcbank", d3, "ICIC008392", "SUCCESS", "Google Pay", "Footwear"),
        ("414273849201", 620.00, "Deepak Joshi", "deepak.j@paytm", "shopeasy@hdfcbank", d4, "PAYTM84920", "SUCCESS", "Paytm", "Snacks & beverages"),
        ("413284910293", 4500.00, "Meera Kulkarni", "meera.k@ybl", "shopeasy@hdfcbank", d4, "YESB009182", "SUCCESS", "PhonePe", "Hardware tools"),
        ("412384920192", 120.00, "Suresh Patel", "suresh.patel@okaxis", "shopeasy@hdfcbank", d5, "UTIB009182", "SUCCESS", "Google Pay", "Breakfast"),
        ("411273849102", 3200.00, "Kavita Reddy", "kavita.reddy@icici", "shopeasy@hdfcbank", d5, "ICIC007182", "SUCCESS", "CRED", "Luxury perfume"),
        ("410293847192", 890.00, "Amitabh Sen", "amitabh.sen@sbi", "shopeasy@hdfcbank", d6, "SBIN002910", "SUCCESS", "BHIM", "Books"),
        ("409182736451", 175.00, "Divya Chauhan", "divya.c@paytm", "shopeasy@hdfcbank", d6, "PAYTM38192", "SUCCESS", "Paytm", "Cafe coffee"),
        ("408273645192", 2800.00, "Rajesh Kumar", "rajesh.k@ybl", "shopeasy@hdfcbank", d6, "YESB004729", "SUCCESS", "PhonePe", "Auto parts"),
        ("407182930192", 950.00, "Sneha Deshmukh", "sneha.d@okhdfcbank", "shopeasy@hdfcbank", d0, "HDFC003819", "SUCCESS", "Google Pay", "Dry fruits"),
        ("406271829301", 150.00, "Manish Tiwari", "manish.t@okaxis", "shopeasy@hdfcbank", d1, "UTIB003719", "SUCCESS", "Google Pay", "Vegetables"),
        ("405192837461", 5200.00, "Praveen Jain", "praveen.j@icici", "shopeasy@hdfcbank", d2, "ICIC004819", "SUCCESS", "CRED", "Watch repair"),
        ("404182938471", 310.00, "Geeta Pandey", "geeta.p@paytm", "shopeasy@hdfcbank", d3, "PAYTM27182", "SUCCESS", "Paytm", "Cosmetics"),
        ("403192837465", 7200.00, "Harish Verma", "harish.v@ybl", "shopeasy@hdfcbank", d3, "YESB003819", "SUCCESS", "PhonePe", "Home appliance"),
        ("402182938472", 480.00, "Bhavna Shah", "bhavna.s@okhdfcbank", "shopeasy@hdfcbank", d4, "HDFC004829", "SUCCESS", "Google Pay", "Bakery items"),
        ("401293847561", 1850.00, "Naveen Choudhary", "naveen.c@okicici", "shopeasy@hdfcbank", d4, "ICIC005829", "SUCCESS", "Google Pay", "Sports goods"),
        ("399182736452", 65.00, "Anita Saxena", "anita.s@paytm", "shopeasy@hdfcbank", d5, "PAYTM18273", "SUCCESS", "Paytm", "Newspaper & stationary"),
        ("398273645193", 1100.00, "Gaurav Singhal", "gaurav.s@ybl", "shopeasy@hdfcbank", d5, "YESB001827", "SUCCESS", "PhonePe", "Plumbing fixtures"),
        ("397182930194", 2300.00, "Shweta Agarwal", "shweta.a@axisbank", "shopeasy@hdfcbank", d6, "UTIB004829", "SUCCESS", "BHIM", "Bedding"),
        ("396271829305", 420.00, "Abhishek Bose", "abhishek.b@okaxis", "shopeasy@hdfcbank", d0, "UTIB002819", "SUCCESS", "Google Pay", "Tea & snacks"),
        ("395192837466", 8900.00, "Tanvi Bhatt", "tanvi.b@okhdfcbank", "shopeasy@hdfcbank", d1, "HDFC008392", "SUCCESS", "CRED", "Smart band"),
        ("394182938477", 260.00, "Ritu Srivastava", "ritu.s@paytm", "shopeasy@hdfcbank", d2, "PAYTM92817", "SUCCESS", "Paytm", "Fruits"),
        ("393192837468", 1350.00, "Alok Mishra", "alok.m@ybl", "shopeasy@hdfcbank", d3, "YESB005829", "SUCCESS", "PhonePe", "Kitchenware"),
        ("392182938479", 99.00, "Sanjay Pillai", "sanjay.p@sbi", "shopeasy@hdfcbank", d4, "SBIN005829", "SUCCESS", "BHIM", "Stationery gift"),
        ("391293847570", 3750.00, "Neha Ganguly", "neha.g@okicici", "shopeasy@hdfcbank", d5, "ICIC006829", "SUCCESS", "Google Pay", "Art supplies")
    ]

    for rec in demo_records:
        cursor.execute(
            """
            INSERT OR IGNORE INTO ledger 
            (txn_id, amount, payer_name, payer_vpa, payee_vpa, timestamp, bank_ref, status, app_source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rec,
        )


def insert_ledger_record(data: Dict[str, Any]) -> int:
    """Inserts a new transaction into the mock ledger table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ledger (txn_id, amount, payer_name, payer_vpa, payee_vpa, timestamp, bank_ref, status, app_source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(data.get("txn_id", "")).strip(),
            float(data.get("amount", 0.0)),
            data.get("payer_name") or "Customer",
            data.get("payer_vpa") or "customer@upi",
            data.get("payee_vpa") or "merchant@bank",
            data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("bank_ref") or ("REF" + str(data.get("txn_id", ""))[-6:]),
            data.get("status") or "SUCCESS",
            data.get("app_source") or "UPI",
            data.get("notes") or "Manual entry",
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_ledger_records(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent trusted records from the ledger."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_ledger_record(txn_id: str) -> Optional[Dict[str, Any]]:
    """Queries trusted ledger by transaction/UTR ID."""
    if not txn_id:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ledger WHERE txn_id = ?", (txn_id.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def log_scan_result(scan_data: Dict[str, Any]) -> int:
    """Logs an analysis result into the scans history table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO scans (
            scan_id, phash, extracted_txn_id, extracted_amount, extracted_date,
            extracted_sender, extracted_receiver, extracted_app, risk_score,
            verdict, verdict_reasons, checks_json, match_json, ela_image_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scan_data.get("scan_id"),
            scan_data.get("phash"),
            scan_data.get("extracted_txn_id"),
            scan_data.get("extracted_amount"),
            scan_data.get("extracted_date"),
            scan_data.get("extracted_sender"),
            scan_data.get("extracted_receiver"),
            scan_data.get("extracted_app"),
            scan_data.get("risk_score"),
            scan_data.get("verdict"),
            json.dumps(scan_data.get("verdict_reasons", [])),
            json.dumps(scan_data.get("checks_json", [])),
            json.dumps(scan_data.get("match_json", {})),
            scan_data.get("ela_image_name"),
        ),
    )
    conn.commit()
    scan_id_pk = cursor.lastrowid
    conn.close()
    return scan_id_pk


def get_all_scans(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves historical scans."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        item = dict(r)
        try:
            item["verdict_reasons"] = json.loads(item.get("verdict_reasons") or "[]")
        except Exception:
            item["verdict_reasons"] = []
        try:
            item["checks_json"] = json.loads(item.get("checks_json") or "[]")
        except Exception:
            item["checks_json"] = []
        try:
            item["match_json"] = json.loads(item.get("match_json") or "{}")
        except Exception:
            item["match_json"] = {}
        results.append(item)
    return results


def find_similar_phash_scans(target_phash: str) -> List[Dict[str, Any]]:
    """Returns past scans containing a perceptual hash for duplicate comparison."""
    if not target_phash:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, scan_id, phash, extracted_txn_id, extracted_amount, created_at FROM scans WHERE phash IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
