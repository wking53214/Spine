"""A kernel root into the artifact the gateway judges: the second hand-off of the evidence spine.

The gateway accepts an artifact only with an authority, and it will check that authority only if it is given a
verifier. Neither is Spine's to decide. The authority a door carries is the deployment's: it is a required keyword
here, with no default, so Spine cannot mint authority for anyone. Spine only says which artifact the gateway is asked
about: the root's digest and the digest of the root's content, under the source it came from.
"""

from __future__ import annotations

import hashlib

from conservation_kernel import Artifact as RootArtifact
from governance_gateway.models import Artifact as DoorArtifact
from governance_gateway.models import Authority, EpistemicStatus, Scope

__all__ = ["door"]


def door(root: RootArtifact, source_id: str, *, authority: Authority) -> DoorArtifact:
    """The artifact the gateway judges for this root. `authority` is required and comes from the deployment."""
    if not isinstance(authority, Authority):
        raise TypeError("door needs the deployment's Authority: Spine never supplies one")
    return DoorArtifact.create(
        artifact_id=f"door:{source_id}",
        payload={"root": root.artifact_digest, "content_sha256": hashlib.sha256(root.content.encode("utf-8")).hexdigest()},
        provenance={"origin": "conservation_kernel", "source_id": source_id},
        epistemic_status=EpistemicStatus.INFERENCE,
        authority=authority,
        scope=Scope.READ_ONLY,
    )
