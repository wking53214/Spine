"""The document into the attempt CCC judges: the third hand-off of the evidence spine, and how CCC's doors are read.

HERALD's reading is taken into CCC as material of UNKNOWN standing by a model actor. Not INFERENCE: since CCC #51,
`ingest` takes material in and refuses to make a conclusion (CCC-EPISTEMIC-001), and a model may not enter material as
evidence or as a human-established record (CCC-RATIFICATION-001). A conclusion about it is made later by `derive`,
`infer` or `interpret`, which keep the evidence it rests on and ask the permission themselves.

The second half says which direct writes to a CCC built with a roster's permission carry a document the roster judged
(`ingest`, `record`) and which carry something no seat judges. `ccc_doors_all_named` holds that list to the doors CCC
really gates, so a door CCC starts gating that this list does not name goes red instead of staying shut unnoticed.
"""

from __future__ import annotations

import hashlib
from typing import Tuple

from ccc.cns_connector import Attempt, write_request_digest
from ccc.cns_connector import attempt as ccc_attempt
from ccc.models import Actor as CccActor
from ccc.models import EpistemicStatus as CccStatus
from ccc.permission import WriteRequest
from ccc.system import CCCSystem

__all__ = ["WRITES_A_DOCUMENT", "WRITES_NO_DOCUMENT", "binds_write", "ccc_doors_all_named", "ccc_gated_doors",
           "ccc_ingest", "reads_write"]

#: The direct writes to CCC that carry a document the roster judged.
WRITES_A_DOCUMENT = ("ingest", "record")

#: The direct writes to CCC that carry something no seat of the roster judges: a conclusion (`derive`, `infer`,
#: `interpret`), a finding (`record_external_finding`, `discover`), an observation (`detect_road_sign`,
#: `record_road_sign`) or a link between records (`attach_evidence`, `relate`). None carries the text the roster
#: compared, so no roster decision opens them. CCC does not ask the roster about operations that act on an existing
#: record or that a person performs (`accept`, `reject`, `decide`, `correct`, `amend`, `supersede`, `redact`, `erase`
#: and the rest); they ask CCC's human verifier instead, so they are not listed here.
WRITES_NO_DOCUMENT = ("derive", "infer", "interpret", "record_external_finding", "discover", "detect_road_sign",
                      "record_road_sign", "attach_evidence", "relate")


def ccc_ingest(text: str, source_id: str, **more) -> Attempt:
    """The attempt CCC judges for this document. `more` overrides what the attempt asks CCC to record."""
    return ccc_attempt("ingest", text, actor=CccActor.model("herald"), epistemic_status=CccStatus.UNKNOWN,
                       metadata={"source_id": source_id}, reason="document read by HERALD", **more)


def reads_write(request: WriteRequest):
    """The document a direct write to CCC is about, as (source id, text digest).

    `ingest` and `record` carry one. The doors in `WRITES_NO_DOCUMENT` carry a conclusion, a finding or an
    observation, which no seat judges, so they name no document and stay refused after any decision. A door that is in
    neither list is refused too: an unknown door stays shut."""
    from cns_composition.super_gate import Judged

    if request.operation in WRITES_A_DOCUMENT:
        return Judged(request.kwargs["metadata"]["source_id"], hashlib.sha256(request.args[0].encode("utf-8")).hexdigest())
    if request.operation in WRITES_NO_DOCUMENT:
        raise ValueError(f"{request.operation} names no document the roster judged: it carries a conclusion, a "
                         "finding or an observation, and no seat judges those")
    raise ValueError(f"{request.operation} is a door the roster has no reading for, so it stays shut")


def binds_write(request: WriteRequest) -> Tuple[str, str]:
    """What a direct write to CCC must be bound to: the same subject and digest CCC's verdict on the attempt carries.

    The operation is the subject and the digest covers the operation and every argument with its defaults applied, so
    `record` where `ingest` was judged, another actor, another status or any other changed argument does not match."""
    return request.operation, write_request_digest(request)


def ccc_gated_doors() -> Tuple[str, ...]:
    """Every public method of CCC that asks its write permission, found on CCC itself, sorted.

    CCC wraps each with its permission decorator, which keeps the method's own name and a pointer to the method it
    wraps. Human-only methods are wrapped by a different decorator (the human verifier), so the wrapper's code is
    checked too: only the permission decorator's wrapper counts. The list is CCC's own, not copied here."""
    def asks_permission(method) -> bool:
        wrapper = getattr(method, "__code__", None)
        return wrapper is not None and wrapper.co_qualname.startswith("_asks_permission.")

    return tuple(sorted(name for name in dir(CCCSystem)
                        if callable(getattr(CCCSystem, name))
                        and hasattr(getattr(CCCSystem, name), "__wrapped__")
                        and getattr(CCCSystem, name).__qualname__ == f"CCCSystem.{name}"
                        and asks_permission(getattr(CCCSystem, name))))


def ccc_doors_all_named() -> str:
    """Empty if `reads_write` has a reading for exactly the doors CCC gates, else what differs."""
    named, gated = set(WRITES_A_DOCUMENT) | set(WRITES_NO_DOCUMENT), set(ccc_gated_doors())
    parts = []
    if gated - named:
        parts.append("CCC gates doors the reader does not name: " + ", ".join(sorted(gated - named)))
    if named - gated:
        parts.append("the reader names doors CCC does not gate: " + ", ".join(sorted(named - gated)))
    return "; ".join(parts)
