"""The real upstream hops for the tests: HERALD reads a document, TIE takes its signed export as evidence.

Nothing here is a stand-in for a Spine hand-off. HERALD and TIE run as they ship; the key that signs the export is
generated per run and TIE pins only its public half.
"""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from herald import ConfidenceGate, build_handoff
from herald.cns_connector import run_governed
from herald.source import STANDING_RECORD, SourceDocument
from tie.evidence.herald_intake import evidence_from_herald_export
from tie.evidence.herald_intake import export_key_id as tie_export_key_id
from tie.models import SourceRecord

INVOICE = ("Invoice INV-2207 dated 2026-03-04 came to $412.00 for the burst kitchen pipe. "
           "Payment of $412.00 was received on 2026-03-11.")
INFLATED = ("Invoice INV-2207 dated 2026-03-04 came to $4,120.00 for the burst kitchen pipe. "
            "Payment of $4,120.00 was received on 2026-03-11.")

EXPORT_KEY = Ed25519PrivateKey.generate()
TRUSTED_KEYS = {tie_export_key_id(EXPORT_KEY.public_key()): EXPORT_KEY.public_key()}


def herald_read(text: str = INVOICE, source_id: str = "doc-1"):
    """HERALD's governed run and its signed export: (document, gate, claims, export)."""
    document = SourceDocument(source_id=source_id, text=text, standing=STANDING_RECORD)
    gate = ConfidenceGate()
    claims = [claim for claim, _ in run_governed(document, confidence_gate=gate).verdicts]
    decisions = [gate.submit(claim, document=document, confirmation=None) for claim in claims]
    export = build_handoff(claims, decisions, document, export_signing_key=EXPORT_KEY).to_dict()
    return document, gate, claims, export


def tie_evidence(export: dict, source_id: str = "doc-1", text: str = INVOICE) -> list:
    """TIE's intake of the export, as TIE ships it. Raises HeraldIntakeRefused if TIE refuses."""
    return evidence_from_herald_export(SourceRecord(source_id=source_id, content=text), export,
                                       trusted_keys=TRUSTED_KEYS)
