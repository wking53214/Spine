"""The three hand-offs, one at a time, against the real repositories on either side."""

from __future__ import annotations

import dataclasses

import pytest
from ccc.models import EpistemicStatus as CccStatus
from ccc.permission import WriteRequest
from conservation_kernel import Actor
from conservation_kernel.enums import EvidenceKind
from conservation_kernel.errors import RootAdmissionError
from governance_gateway.models import Authority

from chain import INFLATED, INVOICE, herald_read, tie_evidence
from spine import (BINDINGS, READERS, SEATS, WRITES_A_DOCUMENT, WRITES_NO_DOCUMENT, ccc_doors_all_named,
                   ccc_gated_doors, ccc_ingest, door, kernel_evidence, kernel_root, reads_write, tie_detail,
                   tie_evidence_guard)

AUTHORITY = Authority(actor="a-deployment", grant="read")


def _evidence():
    document, gate, claims, export = herald_read()
    return document, gate, claims, tie_evidence(export)


def _say_yes(artifact) -> bool:
    return True


def _say_no(artifact) -> bool:
    return False


# --- TIE -> kernel ----------------------------------------------------------------------------------------------

def test_tie_produced_evidence_and_it_names_the_source_it_was_verified_against():
    document, _, _, evidence = _evidence()
    assert evidence
    for record in evidence:
        detail = tie_detail(record)
        assert detail["source_id"] == document.source_id
        assert detail["source_sha256"]  # TIE's own typed read of the verified hash, never the caller's text


def test_the_guard_permits_every_record_tie_produced_and_the_kernel_takes_them():
    document, _, _, evidence = _evidence()
    kernel, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    for n, record in enumerate(evidence):
        assert kernel.registry.evidence(record.evidence_id) is not None
        assert tie_evidence_guard(evidence, document.source_id)(kernel_evidence(record, f"p{n}")) is True
    assert len(root.propositions) == len(evidence)


def test_every_proposition_of_the_root_cites_evidence_about_itself():
    document, _, _, evidence = _evidence()
    kernel, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    for prop in root.propositions:
        cited = [kernel.registry.evidence(ref) for ref in prop.evidence_refs]
        assert cited and all(item.subject_id == prop.proposition_id for item in cited)


@pytest.mark.parametrize("change", [
    {"evidence_id": "ev-invented"},
    {"kind": EvidenceKind.INDEPENDENT_VERIFICATION},
    {"provided_by": Actor.external("someone-else", "not the intake")},
    {"active": False},
    {"subject_id": "p-somewhere-else"},
    {"detail": {"source_id": "doc-1", "source_sha256": "0" * 64, "statement_sha256": "0" * 64}},
])
def test_the_guard_refuses_a_record_that_is_not_exactly_what_tie_produced(change):
    document, _, _, evidence = _evidence()
    guard = tie_evidence_guard(evidence, document.source_id)
    genuine = kernel_evidence(evidence[0], "p0")
    assert guard(genuine) is True
    assert guard(dataclasses.replace(genuine, **change)) is False


def test_the_guard_refuses_evidence_from_a_source_it_was_not_built_for():
    _, _, _, evidence = _evidence()
    guard = tie_evidence_guard(evidence, "some-other-source")
    assert all(guard(kernel_evidence(record, f"p{n}")) is False for n, record in enumerate(evidence))


def test_the_kernel_refuses_evidence_tie_did_not_produce():
    document, _, _, evidence = _evidence()
    kernel, _ = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    forged = dataclasses.replace(kernel_evidence(evidence[0], "p0"), evidence_id="ev-forged-independent-check")
    with pytest.raises(Exception):  # noqa: B017 - the registry's refusal; its type is the kernel's to name
        kernel.registry.add_evidence(forged)
    assert kernel.registry.evidence("ev-forged-independent-check") is None


def test_no_kernel_is_built_without_the_deployments_root_guard():
    document, _, _, evidence = _evidence()
    with pytest.raises(TypeError):
        kernel_root(evidence, document.source_id, INVOICE, root_guard=None)
    with pytest.raises(TypeError):
        kernel_root(evidence, document.source_id, INVOICE, root_guard="yes")  # type: ignore[arg-type]


def test_the_kernel_asks_the_guard_it_was_given_before_registering_a_root():
    document, _, _, evidence = _evidence()
    asked = []

    def guard(artifact) -> bool:
        asked.append(artifact.artifact_id)
        return False

    kernel, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=guard)
    with pytest.raises(RootAdmissionError):
        kernel.register_root(root)
    assert asked == [root.artifact_id]


def test_a_root_the_guard_allows_is_registered():
    document, _, _, evidence = _evidence()
    kernel, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_yes)
    kernel.register_root(root)


# --- kernel -> gateway ------------------------------------------------------------------------------------------

def test_the_door_carries_exactly_the_authority_the_deployment_gave_it():
    document, _, _, evidence = _evidence()
    _, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    entry = door(root, document.source_id, authority=AUTHORITY)
    assert entry.authority == AUTHORITY
    assert entry.provenance["source_id"] == document.source_id
    assert entry.payload["root"] == root.artifact_digest


def test_spine_never_supplies_an_authority():
    document, _, _, evidence = _evidence()
    _, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    with pytest.raises(TypeError):
        door(root, document.source_id)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        door(root, document.source_id, authority="read")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        door(root, document.source_id, authority=None)  # type: ignore[arg-type]


# --- document -> CCC --------------------------------------------------------------------------------------------

def test_ccc_is_asked_to_ingest_the_document_as_material_of_unknown_standing():
    attempt = ccc_ingest(INVOICE, "doc-1")
    assert attempt.subject == "ingest"
    assert attempt.args[0] == INVOICE
    assert attempt.kwargs["metadata"] == {"source_id": "doc-1"}
    assert attempt.kwargs["epistemic_status"] is CccStatus.UNKNOWN


def test_a_direct_write_that_carries_a_document_is_read_as_that_document():
    request = WriteRequest(operation="ingest", args=(INVOICE,), kwargs={"metadata": {"source_id": "doc-1"}})
    read = reads_write(request)
    assert read == READERS["CCC:ccc.transition"](ccc_ingest(INVOICE, "doc-1"))


@pytest.mark.parametrize("operation", WRITES_NO_DOCUMENT)
def test_a_write_that_carries_no_document_is_never_read_as_one(operation):
    with pytest.raises(ValueError):
        reads_write(WriteRequest(operation=operation, args=("x",), kwargs={}))


def test_an_unknown_door_stays_shut():
    with pytest.raises(ValueError):
        reads_write(WriteRequest(operation="a-door-nobody-named", args=("x",), kwargs={}))


def test_every_door_ccc_gates_is_named_and_none_named_is_gone():
    assert ccc_doors_all_named() == ""
    assert set(ccc_gated_doors()) == set(WRITES_A_DOCUMENT) | set(WRITES_NO_DOCUMENT)


# --- the readings -----------------------------------------------------------------------------------------------

def test_the_five_readings_cover_the_five_seats():
    assert set(READERS) == set(BINDINGS) == set(SEATS)
    assert len(SEATS) == 5


def test_every_hop_reads_the_same_document_when_it_is_the_same_document():
    document, _, claims, evidence = _evidence()
    _, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    entry = door(root, document.source_id, authority=AUTHORITY)
    reads = {
        "HERALD:herald_source": READERS["HERALD:herald_source"](document),
        "Conservation_Kernel:root_admission": READERS["Conservation_Kernel:root_admission"](root),
        "Governance_Gateway:governance_gateway": READERS["Governance_Gateway:governance_gateway"](entry),
        "CCC:ccc.transition": READERS["CCC:ccc.transition"](ccc_ingest(INVOICE, document.source_id)),
    }
    assert len({(r.identity, r.digest) for r in reads.values()}) == 1


def test_a_hop_that_is_handed_another_text_reads_another_document():
    document, _, _, evidence = _evidence()
    _, root = kernel_root(evidence, document.source_id, INVOICE, root_guard=_say_no)
    true_read = READERS["Conservation_Kernel:root_admission"](root)
    inflated = READERS["CCC:ccc.transition"](ccc_ingest(INFLATED, document.source_id))
    assert (inflated.identity, inflated.digest) != (true_read.identity, true_read.digest)
