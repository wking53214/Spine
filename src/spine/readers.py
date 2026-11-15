"""How each hop says which document it is about, and what each seat's verdict must be bound to.

A roster that holds five gates in one decision has to know, for each gate, which document its candidate is about
(`READERS`) and what its verdict must be bound to (`BINDINGS`). Neither is policy about whether to allow anything: they
are readings of the real objects, each with the digest function that object's own repository exports. The five gates
each bind their own verdict to what they judged, and nothing else makes them judge the same document, so these
readings are what lets a roster refuse a decision unless every seat judged the same one.
"""

from __future__ import annotations

import hashlib
from typing import Tuple

from ccc.cns_connector import Attempt, attempt_digest
from cns_composition.super_gate import Judged
from conservation_kernel import Artifact as RootArtifact
from conservation_kernel.cns_connector import DEFAULT_ROOT_SUBJECT, root_digest
from governance_gateway.cns_connector import artifact_digest as door_digest
from governance_gateway.cns_connector import artifact_subject as door_subject
from governance_gateway.models import Artifact as DoorArtifact
from herald.cns_connector import DEFAULT_SOURCE_SUBJECT, DEFAULT_SUBJECT, claim_digest, source_digest
from herald.source import SourceDocument

__all__ = ["BINDINGS", "READERS", "SEATS", "binds_attempt", "binds_claim", "binds_document", "binds_door",
           "binds_root", "reads_attempt", "reads_claim", "reads_document", "reads_door", "reads_root", "sha256"]

#: The seats the five readings below are for, named as a roster names them.
SEATS = ("HERALD:herald_source", "Conservation_Kernel:root_admission", "Governance_Gateway:governance_gateway",
         "HERALD:herald_confidence", "CCC:ccc.transition")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reads_document(document: SourceDocument) -> Judged:
    return Judged(document.source_id, sha256(document.text))


def reads_root(root: RootArtifact) -> Judged:
    """The one source the root's propositions cite, and the digest of the root's content."""
    cited = {ref for proposition in root.propositions for ref in proposition.source_refs}
    return Judged(next(iter(cited)) if len(cited) == 1 else "", sha256(root.content))


def reads_door(entry: DoorArtifact) -> Judged:
    return Judged(entry.provenance["source_id"], entry.payload["content_sha256"])


def reads_attempt(att: Attempt) -> Judged:
    """The source CCC is asked to record the document under, and the digest of the text it is asked to ingest."""
    return Judged(att.kwargs["metadata"]["source_id"], sha256(att.args[0]))


def reads_claim(claim) -> Judged:
    return Judged(claim.source_id, claim.source_hash or "")


#: How each seat's candidate says which document it is about.
READERS = {"HERALD:herald_source": reads_document, "Conservation_Kernel:root_admission": reads_root,
           "Governance_Gateway:governance_gateway": reads_door, "HERALD:herald_confidence": reads_claim,
           "CCC:ccc.transition": reads_attempt}


def binds_document(document: SourceDocument) -> Tuple[str, str]:
    return DEFAULT_SOURCE_SUBJECT, source_digest(document)


def binds_root(root: RootArtifact) -> Tuple[str, str]:
    """What the kernel's verdict on a root is bound to: the root's id and its whole artifact digest."""
    return DEFAULT_ROOT_SUBJECT, root_digest(root)


def binds_door(entry: DoorArtifact) -> Tuple[str, str]:
    return door_subject(entry), door_digest(entry)


def binds_attempt(att: Attempt) -> Tuple[str, str]:
    """What CCC's verdict on an attempt is bound to: the operation and every argument, defaults applied."""
    return att.subject, attempt_digest(att)


def binds_claim(claim) -> Tuple[str, str]:
    return DEFAULT_SUBJECT, claim_digest(claim)


#: What each seat's verdict must be bound to, read with the digest function that seat's own repository exports.
BINDINGS = {"HERALD:herald_source": binds_document, "Conservation_Kernel:root_admission": binds_root,
            "Governance_Gateway:governance_gateway": binds_door, "HERALD:herald_confidence": binds_claim,
            "CCC:ccc.transition": binds_attempt}
