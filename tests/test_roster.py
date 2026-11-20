"""Spine's hand-offs fed to the real gates and the real roster: do the hops connect?

The roster here is the caller's, written in this file the way a deployment writes it: which seats, which authority the
gateway accepts, which guard the kernel gets. Spine supplies only the objects each seat judges and the readings that
say which document each is about.
"""

from __future__ import annotations

import pytest
from ccc.cns_connector import CccGate
from ccc.errors import WritePermissionRefused
from ccc.models import Actor as CccActor
from ccc.models import EpistemicStatus as CccStatus
from ccc.system import CCCSystem
from cns.gate import GateOutcome
from cns_composition.decision_guard import DecisionGuard
from cns_composition.super_gate import SuperGate
from conservation_kernel.cns_connector import CnsRootAdmissionGate
from governance_gateway.cns_connector import CnsGate as GatewayGate
from governance_gateway.gateway import GovernanceGateway
from governance_gateway.models import Authority
from herald.cns_connector import HeraldConfidenceGate, HeraldSourceGate

from chain import INFLATED, INVOICE, herald_read, tie_evidence
from spine import BINDINGS, READERS, binds_write, ccc_ingest, door, kernel_root, reads_write

DEPLOYMENT_AUTHORITY = Authority(actor="a-deployment", grant="read")
REQUIRED = ("HERALD:herald_source", "Conservation_Kernel:root_admission", "Governance_Gateway:governance_gateway",
            "HERALD:herald_confidence", "CCC:ccc.transition", "CNS:same_subject")


def _decide(*, ccc_text: str = INVOICE, authority: Authority = DEPLOYMENT_AUTHORITY, root_text: str = INVOICE):
    """The roster over a CCC built with both safety opt-outs on, as the first four tests have always run it."""
    return _roster(ccc_text=ccc_text, authority=authority, root_text=root_text, safe=False)[0]


def _roster(*, ccc_text: str, authority: Authority, root_text: str, safe: bool):
    """(decision, CCC system, the write permission or None). With safe=True CCC is built the way a deployment builds it:
    a write permission that is a DecisionGuard, a human verifier that refuses every human act, neither opt-out given,
    and the CCC seat refuses a system that has no permission or one that is not a DecisionGuard."""
    document, gate, claims, export = herald_read()
    evidence = tie_evidence(export)
    kernel, root = kernel_root(evidence, document.source_id, root_text, root_guard=lambda artifact: True)
    entry = door(root, document.source_id, authority=authority)
    gateway = GovernanceGateway(authority_verifier=lambda held: held == DEPLOYMENT_AUTHORITY)
    guard = None
    if safe:
        guard = DecisionGuard(subject_of=reads_write, seat="CCC:ccc.transition", binding_of=binds_write,
                              expected_seats=REQUIRED, require_strict_binding=True)
        system = CCCSystem(write_permission=guard, human_verifier=lambda request: False)
        ccc_gate = CccGate(system, require_permission=True, accept_permission=lambda held: isinstance(held, DecisionGuard))
    else:
        system = CCCSystem(allow_unguarded_writes=True, allow_unverified_humans=True)
        ccc_gate = CccGate(system)
    amount = next(c for c in claims if c.kind == "amount")
    steps = [("HERALD", HeraldSourceGate(), document),
             ("Conservation_Kernel", CnsRootAdmissionGate(kernel, require_guard=True, require_evidence_guard=True,
                                                          require_statement_binding=True), root),
             ("Governance_Gateway", GatewayGate(inner=gateway), entry),
             ("CCC", ccc_gate, ccc_ingest(ccc_text, document.source_id)),
             ("HERALD", HeraldConfidenceGate(gate, document=document), amount)]
    seats = [(repo, g) for repo, g, _ in steps]
    decision = SuperGate(seats, required=REQUIRED, same_subject=dict(READERS), binding_of=dict(BINDINGS),
                         strict_binding=True).decide({f"{repo}:{g.name}": c for repo, g, c in steps})
    return decision, system, guard


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


def test_the_roster_allows_the_true_document_over_a_ccc_built_with_both_safety_switches_on():
    """The same document and the same roster, with CCC built without either opt-out. The one write the roster judged
    goes through once, and only that write."""
    decision, system, guard = _roster(ccc_text=INVOICE, authority=DEPLOYMENT_AUTHORITY, root_text=INVOICE, safe=True)
    assert decision.allowed and not decision.run.blocking()
    ingest = dict(actor=CccActor.model("herald"), epistemic_status=CccStatus.UNKNOWN,
                  metadata={"source_id": "doc-1"}, reason="document read by HERALD")
    with pytest.raises(WritePermissionRefused):  # before the decision is handed to the guard, nothing is permitted
        system.ingest(INVOICE, **ingest)
    guard.authorize(decision)
    with pytest.raises(WritePermissionRefused):  # the guard opens for the text the roster judged, not another
        system.ingest(INFLATED, **ingest)
    system.ingest(INVOICE, **ingest)
    with pytest.raises(WritePermissionRefused):  # one decision opens one write
        system.ingest(INVOICE, **ingest)


def test_the_ccc_seat_refuses_a_ccc_that_has_no_write_permission_when_it_is_asked_to_require_one():
    document, *_ = herald_read()
    system = CCCSystem(allow_unguarded_writes=True, human_verifier=lambda request: False)
    verdict = CccGate(system, require_permission=True).check(ccc_ingest(INVOICE, document.source_id))
    assert verdict.outcome is not GateOutcome.PASS
