"""Spine's hand-offs fed to the real gates and the real roster: do the hops connect?

The roster here is the caller's, written in this file the way a deployment writes it: which seats, which authority the
gateway accepts, which guard the kernel gets. Spine supplies only the objects each seat judges and the readings that
say which document each is about.
"""

from __future__ import annotations

import pytest
from ccc.cns_connector import CccGate
from ccc.system import CCCSystem
from cns.gate import GateOutcome
from cns_composition.super_gate import SuperGate
from conservation_kernel.cns_connector import CnsRootAdmissionGate
from governance_gateway.cns_connector import CnsGate as GatewayGate
from governance_gateway.gateway import GovernanceGateway
from governance_gateway.models import Authority
from herald.cns_connector import HeraldConfidenceGate, HeraldSourceGate

from chain import INFLATED, INVOICE, herald_read, tie_evidence
from spine import BINDINGS, READERS, ccc_ingest, door, kernel_root

DEPLOYMENT_AUTHORITY = Authority(actor="a-deployment", grant="read")
REQUIRED = ("HERALD:herald_source", "Conservation_Kernel:root_admission", "Governance_Gateway:governance_gateway",
            "HERALD:herald_confidence", "CCC:ccc.transition", "CNS:same_subject")


def _decide(*, ccc_text: str = INVOICE, authority: Authority = DEPLOYMENT_AUTHORITY, root_text: str = INVOICE):
    document, gate, claims, export = herald_read()
    evidence = tie_evidence(export)
    kernel, root = kernel_root(evidence, document.source_id, root_text, root_guard=lambda artifact: True)
    entry = door(root, document.source_id, authority=authority)
    gateway = GovernanceGateway(authority_verifier=lambda held: held == DEPLOYMENT_AUTHORITY)
    system = CCCSystem(allow_unguarded_writes=True, allow_unverified_humans=True)
    amount = next(c for c in claims if c.kind == "amount")
    steps = [("HERALD", HeraldSourceGate(), document),
             ("Conservation_Kernel", CnsRootAdmissionGate(kernel, require_guard=True, require_evidence_guard=True,
                                                          require_statement_binding=True), root),
             ("Governance_Gateway", GatewayGate(inner=gateway), entry),
             ("CCC", CccGate(system), ccc_ingest(ccc_text, document.source_id)),
             ("HERALD", HeraldConfidenceGate(gate, document=document), amount)]
    seats = [(repo, g) for repo, g, _ in steps]
    return SuperGate(seats, required=REQUIRED, same_subject=dict(READERS), binding_of=dict(BINDINGS),
                     strict_binding=True).decide({f"{repo}:{g.name}": c for repo, g, c in steps})


def test_the_true_document_passes_every_seat_and_the_roster_allows_it():
    decision = _decide()
    assert decision.run.outcome is GateOutcome.PASS
    assert decision.allowed
    assert not decision.run.blocking()


def test_ccc_asked_about_another_text_while_the_others_judge_the_true_one_is_refused_by_the_agreement():
    decision = _decide(ccc_text=INFLATED)
    assert not decision.allowed
    assert "same_subject" in {r.gate for r in decision.run.blocking()}


def test_a_door_carrying_an_authority_the_gateway_does_not_hold_is_refused_by_the_gateway():
    decision = _decide(authority=Authority(actor="someone-else", grant="read"))
    assert not decision.allowed
    assert "governance_gateway" in {r.gate for r in decision.run.blocking()}


def test_a_root_built_from_another_text_than_the_others_judged_is_refused():
    decision = _decide(root_text=INFLATED)
    assert not decision.allowed
    assert {r.gate for r in decision.run.blocking()} & {"same_subject", "root_admission"}


@pytest.mark.parametrize("seat", [s for s in REQUIRED if s != "CNS:same_subject"])
def test_the_five_seats_are_all_read_and_bound_by_spine(seat):
    assert seat in READERS and seat in BINDINGS
