# Spine

The production hand-offs of the evidence spine. One document goes through five repositories, in order:

| hop | what it does with the document |
|---|---|
| HERALD | reads it and extracts claims, judging the document first and then each claim |
| TIE | records HERALD's signed export as evidence, and refuses an export that was changed |
| Conservation_Kernel | judges a root artifact built from that evidence before it becomes ancestry |
| Governance_Gateway | judges the artifact at its admission door |
| CCC | judges the attempt to take the document into its store |

Each repository is tested alone and none imports another. What no single suite can see is the seams: whether the
evidence that reaches the kernel is the evidence TIE produced, and whether the artifact at the gateway and the attempt
at CCC are about the document HERALD read. **Spine is the one place that imports them together** and says how one hop's
output becomes the next hop's input. Until now those three steps were written inside a test script in CNS
(`chains/evidence_spine.py`); this repository is where a production caller gets them.

## What is here

| module | hand-off |
|---|---|
| `spine.evidence` | TIE evidence to kernel objects: `kernel_root`, `kernel_evidence`, `tie_evidence_guard` |
| `spine.door` | a kernel root to the artifact the gateway judges: `door` |
| `spine.ccc` | the document to the attempt CCC judges: `ccc_ingest`, and which CCC writes carry a document |
| `spine.readers` | `READERS` and `BINDINGS`: which document each seat's candidate is about, and what its verdict is bound to |

## What is not here, on purpose

Spine holds **no key and no policy**.

- The kernel's root guard and the gateway's authority are **required arguments with no default**
  (`kernel_root(..., root_guard=)`, `door(..., authority=)`). Spine never builds an unguarded kernel and never mints an
  authority for anyone. Passing none is a `TypeError`.
- The roster that combines the five verdicts, its required seats, and the permissions that act on its decision are the
  deployment's. Spine supplies the objects each seat judges and the readings that let a roster refuse a decision unless
  every seat judged the same document.
- Evidence is checked against TIE's own record, never against the caller's account of the text: the source hash comes
  from TIE's typed `source_sha256_of`. A record TIE did not produce, one about another source, one with altered
  metadata, or one of another kind is refused.

Spine is not an authority and not an orchestrator. It does not decide whether a document may pass. It supplies what a
roster needs to check that the five gates are being asked about the same document. Spine does not make that check
itself.

Checked 2026-11-18 at the pinned commits (EXECUTED). With a root guard that says yes, `kernel_root` builds, and the
kernel registers, a root whose content is a different text from the one TIE verified. That mismatch is caught only by
a roster that compares the seats' readings, as `tests/test_roster.py` does. With no TIE evidence at all, `kernel_root`
still returns a root of one uncited proposition at the default INFERENCE status, and the kernel registers it; the same
root as a FACT is refused.

## Install and test

```
pip install ".[dev]"
pytest -q
```

Every dependency is pinned to an exact commit in `pyproject.toml`, so an install gets the same code every time; moving a
pin is a reviewed change. `tests/test_roster.py` feeds Spine's output to the real gates and a real roster and checks the
refusals: another text at CCC, an authority the gateway does not hold, a root built from other words. It runs the roster twice over CCC: once with CCC's two safety opt-outs on, and once built the way a deployment builds it (a write permission and a human verifier, no opt-outs), where the one write the roster judged goes through once and nothing else does. All six pins were moved together on 2026-11-19 and the 43 tests pass in a fresh install at them (EXECUTED).

## What this does not prove

That the five repositories are wired into a running service: there is none yet. That the deployment's guard and authority
are good ones: they are the deployment's. The in-process limit stands: code in the same process can reach past a guard;
guards protect callers outside it.
