"""TIE evidence into kernel objects: the first hand-off of the evidence spine.

TIE records HERALD's signed export as evidence; the Conservation_Kernel judges a root artifact built from it. No
repository ships the step between the two, and neither imports the other. This module is that step. It holds no key
and no policy: the kernel's root guard comes from the deployment (a required argument, never a default), and the
evidence guard is exact, derived from TIE's own records.

What it will not do, by construction:

* build a kernel without a root guard or without an evidence guard (there is no opt-out here);
* take a fact about the source from the caller: the source text hash comes from TIE's record, never from the text the
  caller hands in;
* accept a record TIE did not produce, one about another source, one with altered metadata, or one of another kind.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Dict, List, Tuple

from conservation_kernel import Actor, Artifact as RootArtifact, ConservationKernel, EvidenceRecord, Proposition
from conservation_kernel.enums import EpistemicStatus as RootStatus
from conservation_kernel.enums import EvidenceKind, OriginStatus
from tie.evidence.herald_intake import source_sha256_of

__all__ = ["TieEvidenceGuard", "kernel_evidence", "kernel_root", "tie_detail", "tie_evidence_guard"]


class TieEvidenceGuard:
    """The evidence guard, as a kind of object, so a roster can accept this guard and not just any function."""

    def __init__(self, permits: Callable[[EvidenceRecord], bool]) -> None:
        self._permits = permits

    def __call__(self, record: EvidenceRecord) -> bool:
        return self._permits(record)


def tie_detail(record: Any) -> Dict[str, object]:
    """What the kernel's registry should hold for a record TIE produced: derived from TIE's record, never from the
    caller's text."""
    return {"source_id": record.source_ref.source_id, "source_sha256": source_sha256_of(record),
            "statement_sha256": record.statement_sha256}


def kernel_evidence(record: Any, pid: str) -> EvidenceRecord:
    """The kernel's evidence record for one TIE record: the one translation, used to add the record and, in
    `tie_evidence_guard`, to say exactly what may be added under that id. The proposition `pid` it supports is part of
    it, and the detail comes from TIE's own record (`tie_detail`)."""
    return EvidenceRecord(evidence_id=record.evidence_id, subject_id=pid, kind=EvidenceKind.SOURCE_OBSERVATION,
                          provided_by=Actor.model("herald"), detail=tie_detail(record))


def tie_evidence_guard(evidence: List[Any], source_id: str) -> TieEvidenceGuard:
    """The kernel's `evidence_guard`: it permits an evidence record only if TIE produced it, from this source.

    The evidence has to be in the kernel's registry before a roster can decide (the root seat checks that a root's
    citations exist), so no decision exists yet and a decision guard cannot be the permission here. The record must be
    exactly what `kernel_evidence` gives for that id, so an id cannot be taken first with false metadata (its
    provider, its independence, whether it is active, its detail, the proposition it supports). Only `created_at` is
    left out of that comparison, because it is when the record was added; it must still be a time with an offset that
    is not in the future. The guard is not spent by a yes, because one document gives TIE many records."""
    produced = {record.evidence_id for record in evidence}
    expected = {record.evidence_id: kernel_evidence(record, f"p{n}") for n, record in enumerate(evidence)}

    def added_by_now(created_at: object) -> bool:
        try:
            moment = datetime.datetime.fromisoformat(str(created_at))
        except ValueError:
            return False
        return moment.tzinfo is not None and moment <= (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60))

    def whole(record: EvidenceRecord) -> Dict[str, object]:
        return {name: part for name, part in record.to_dict().items() if name != "created_at"}

    def permits(record: EvidenceRecord) -> bool:
        if not (record.evidence_id in produced and record.kind is EvidenceKind.SOURCE_OBSERVATION):
            return False
        detail = expected[record.evidence_id].detail
        return (detail["source_sha256"] is not None and detail["source_id"] == source_id
                and whole(record) == whole(expected[record.evidence_id]) and added_by_now(record.created_at))

    return TieEvidenceGuard(permits)


def kernel_root(evidence: List[Any], source_id: str, text: str, *, root_guard: Callable[[RootArtifact], bool],
                status: RootStatus = RootStatus.INFERENCE) -> Tuple[ConservationKernel, RootArtifact]:
    """TIE evidence to a kernel and the root it supports.

    The kernel is built with the caller's `root_guard` (required) and with the exact evidence guard for this evidence,
    and with `refuse_inactive_root_evidence`. Each TIE record becomes one proposition that cites it. With no evidence
    the root is one proposition citing none, which the kernel will not admit as a FACT."""
    if not callable(root_guard):
        raise TypeError("kernel_root needs the deployment's root_guard: Spine never builds an unguarded kernel")
    kernel = ConservationKernel(root_guard=root_guard, evidence_guard=tie_evidence_guard(evidence, source_id),
                                refuse_inactive_root_evidence=True)
    propositions = []
    for n, record in enumerate(evidence):
        pid = f"p{n}"
        kernel.registry.add_evidence(kernel_evidence(record, pid))
        propositions.append(Proposition(proposition_id=pid, text=record.statement, epistemic_status=status,
                                        origin=OriginStatus.MACHINE_ORIGINATED,
                                        evidence_refs=(record.evidence_id,), source_refs=(source_id,)))
    if not propositions:
        propositions.append(Proposition(proposition_id="p0", text=text, epistemic_status=status,
                                        origin=OriginStatus.MACHINE_ORIGINATED, source_refs=(source_id,)))
    return kernel, RootArtifact(artifact_id=f"root:{source_id}", content=text, propositions=tuple(propositions),
                                producer=Actor.system("tie"))
