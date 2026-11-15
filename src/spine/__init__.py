"""Spine: the production hand-offs of the evidence spine.

HERALD reads a document; TIE records its signed export as evidence; the Conservation_Kernel judges a root built from
that evidence; the Governance_Gateway judges the artifact at its admission door; CCC judges the attempt to take the
document into its store. Each repository is tested alone, and none imports another. Spine is the one place that
imports them together and says how one hop's output becomes the next hop's input.

Spine holds no key and no policy. The kernel's root guard and the gateway's authority are the deployment's and are
required arguments with no default; the roster that combines the five verdicts, and its required seats, are not here.
"""

from spine.ccc import (WRITES_A_DOCUMENT, WRITES_NO_DOCUMENT, binds_write, ccc_doors_all_named, ccc_gated_doors,
                       ccc_ingest, reads_write)
from spine.door import door
from spine.evidence import TieEvidenceGuard, kernel_evidence, kernel_root, tie_detail, tie_evidence_guard
from spine.readers import BINDINGS, READERS, SEATS

__version__ = "0.1.0"

__all__ = ["BINDINGS", "READERS", "SEATS", "TieEvidenceGuard", "WRITES_A_DOCUMENT", "WRITES_NO_DOCUMENT",
           "binds_write", "ccc_doors_all_named", "ccc_gated_doors", "ccc_ingest", "door", "kernel_evidence",
           "kernel_root", "reads_write", "tie_detail", "tie_evidence_guard"]
