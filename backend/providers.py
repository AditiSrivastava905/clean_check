"""Trusted Record Providers for CleanCheck

Defines the abstract interface for transaction verification against trusted sources,
the MockLedgerProvider backed by SQLite for offline hackathon testing, and
the RealProviderStub highlighting production banking/NPCI integration points.

IMPORTANT: Real verification requires authorized bank or NPCI UPI API access.
CleanCheck's architecture strictly decouples forensic analysis from record lookup.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import sys
from pathlib import Path

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DATE_TOLERANCE_DAYS
from backend.db import find_ledger_record, insert_ledger_record, get_ledger_records


class TrustedRecordProvider(ABC):
    """Abstract Base Class for trusted transaction verification providers."""

    @abstractmethod
    def lookup(
        self,
        txn_id: Optional[str],
        amount: Optional[float] = None,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Look up a transaction and verify details.

        Returns a dictionary containing:
            - found (bool): Whether the transaction ID exists in trusted records.
            - matched (bool): Whether all fields (amount, date, status) match.
            - mismatches (list[str]): Detailed explanations of any discrepancy.
            - details (dict | None): Trusted record fields if found.
            - provider_name (str): Identifier for provider.
            - is_demo (bool): True if running in simulated/mock mode.
        """
        pass

    @abstractmethod
    def is_demo(self) -> bool:
        """Returns True if the provider is a simulation/mock."""
        pass


class MockLedgerProvider(TrustedRecordProvider):
    """Local SQLite-backed mock provider for demonstrations and tests.

    Stores a simulated bank ledger with realistic transaction entries.
    Allows local testing of payment verification flows without live banking credentials.
    """

    def is_demo(self) -> bool:
        return True

    def lookup(
        self,
        txn_id: Optional[str],
        amount: Optional[float] = None,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = {
            "found": False,
            "matched": False,
            "mismatches": [],
            "details": None,
            "provider_name": "MockLedgerProvider (Simulated Bank Ledger)",
            "is_demo": True,
        }

        if not txn_id or not str(txn_id).strip():
            result["mismatches"].append("No valid transaction/UTR reference provided for lookup.")
            return result

        clean_txn_id = str(txn_id).strip()
        record = find_ledger_record(clean_txn_id)

        if not record:
            result["mismatches"].append(
                f"Transaction ID '{clean_txn_id}' was not found in trusted records. Money may not have reached the account."
            )
            return result

        result["found"] = True
        result["details"] = {
            "txn_id": record["txn_id"],
            "amount": float(record["amount"]),
            "payer_name": record.get("payer_name"),
            "payer_vpa": record.get("payer_vpa"),
            "payee_vpa": record.get("payee_vpa"),
            "timestamp": record.get("timestamp"),
            "status": record.get("status"),
            "bank_ref": record.get("bank_ref"),
            "app_source": record.get("app_source"),
        }

        # 1. Amount verification
        mismatches: List[str] = []
        if amount is not None:
            ledger_amount = float(record["amount"])
            try:
                extracted_amount = float(amount)
                if abs(ledger_amount - extracted_amount) > 0.01:
                    mismatches.append(
                        f"Amount mismatch: Screenshot displays ₹{extracted_amount:,.2f}, but trusted ledger record has ₹{ledger_amount:,.2f}."
                    )
            except (ValueError, TypeError):
                mismatches.append(f"Invalid extracted amount '{amount}' compared against ledger ₹{ledger_amount:,.2f}.")
        else:
            mismatches.append("Amount could not be extracted from screenshot for comparison.")

        # 2. Status verification
        if record.get("status") != "SUCCESS":
            mismatches.append(f"Ledger records indicate payment status is '{record.get('status')}', not SUCCESS.")

        # 3. Date verification (if date is extracted)
        if date_str and record.get("timestamp"):
            try:
                # Attempt flexible date parsing
                screenshot_dt = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
                    try:
                        screenshot_dt = datetime.strptime(date_str[:10], fmt[: len(date_str[:10])])
                        break
                    except Exception:
                        pass

                if screenshot_dt:
                    ledger_dt = datetime.strptime(record["timestamp"][:10], "%Y-%m-%d")
                    diff_days = abs((screenshot_dt - ledger_dt).days)
                    if diff_days > DATE_TOLERANCE_DAYS:
                        mismatches.append(
                            f"Date discrepancy: Screenshot date ({date_str}) differs from ledger timestamp ({record['timestamp']}) by {diff_days} days."
                        )
            except Exception:
                # Lenient on date parsing failures
                pass

        result["mismatches"] = mismatches
        result["matched"] = (len(mismatches) == 0)
        return result


class RealProviderStub(TrustedRecordProvider):
    """Stub demonstrating how an authorized production banking API plugs in.

    In production, this class implements authenticated integration with:
    - NPCI UPI Unified Dispute & Transaction Status API
    - Authorized Account Aggregator (AA) framework
    - Direct Bank Merchant Webhooks / Core Banking System (CBS) APIs

    Example Headers:
        Authorization: Bearer <BANK_OAUTH_TOKEN>
        X-Merchant-ID: <AUTHORIZED_MERCHANT_KEY>
        X-Signature: HMAC-SHA256(payload, secret)
    """

    def __init__(self, api_endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self.api_endpoint = api_endpoint or "https://api.partnerbank.com/v1/upi/verify"
        self.api_key = api_key

    def is_demo(self) -> bool:
        return False

    def lookup(
        self,
        txn_id: Optional[str],
        amount: Optional[float] = None,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Production stub for authorized bank API call.

        Note: Real verification requires certified bank credentials.
        """
        # Production implementation pattern:
        # payload = {"rrn": txn_id, "amount": amount, "date": date_str}
        # resp = requests.post(self.api_endpoint, json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        # return parse_bank_response(resp.json())

        return {
            "found": False,
            "matched": False,
            "mismatches": [
                "RealProviderStub: Live banking credentials not configured. Switch to MockLedgerProvider for demo testing."
            ],
            "details": None,
            "provider_name": "RealProviderStub (Authorized NPCI / Bank API Gateway)",
            "is_demo": False,
        }
