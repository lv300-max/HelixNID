# HELIXNID Definitions, Lemmas, Theorems, Corollaries

This file is the formal-language layer for HELIXNID.

It states definitions, lemmas, theorems, and corollaries used by the workbench.

## A. Core definitions

### Definition 1 — GridSide

`GridSide = 43`

### Definition 2 — GridCells

`GridCells = GridSide * GridSide = 1849`

### Definition 3 — CellIndex

`CellIndex = { x | 0 <= x < 1849 }`

### Definition 4 — Mirror distance

For any integer x:

`D(x) = min(x, 1849 - x)`

For validated cell indices, D gives the shortest distance to the near/far wall pair.

### Definition 5 — Absolute horizon

`H = floor(1849 / 2) = 924`

### Definition 6 — BaseGrid

Every complete 1849-cell grid has label `BaseGrid`.

### Definition 7 — Prime density rho

`rho = prime_like_cells / 1849`

### Definition 8 — Twist frequency tau

`tau = number_of_lane_switches_within_grid`

### Definition 9 — Constitutional grid label

A grid may receive:

- `Sovereign` if rho > 0.30
- `Anchor` if rho < 0.25
- `Nexus` if tau > 450

### Definition 10 — Gate-7 packet

A Gate-7 packet is a 7-digit chunk extracted from a decimal stream and treated as a fixed-width state unit.

### Definition 11 — Grid hash

A grid hash is a deterministic digest of grid contents, metadata, and parent pointer.

### Definition 12 — Grid-chain

A grid-chain is an ordered sequence of grids where each grid links to the previous grid hash.

### Definition 13 — Implemented Awareness

Implemented Awareness is the live self-state model of the system.

### Definition 14 — Meta-Awareness

Meta-Awareness is the self-check model that inspects whether the awareness state is complete, sourced, permission-safe, memory-safe, and non-conflicted.

### Definition 15 — Operational existence

Operational existence means the system can maintain and report identity, current mode, active goal, permission state, source state, memory continuity pointer, active self-model, and active meta-self-model across tasks.

## B. Lemmas

### Lemma 1 — Grid cell count

`43 * 43 = 1849`

Reason:

43 squared equals 1849.

### Lemma 2 — Mirror pair equality

For x in the valid range:

`D(x) = D(1849 - x)`

Examples:

- D(5) = D(1844) = 5
- D(20) = D(1829) = 20

### Lemma 3 — Horizon bound

For valid x:

`D(x) <= 924`

Reason:

The farthest nearest-wall distance in an odd-length 1849 system is floor(1849/2).

### Lemma 4 — BaseGrid totality

Every complete grid with 1849 cells receives BaseGrid.

### Lemma 5 — Sovereign/Anchor exclusion

A grid cannot be both Sovereign and Anchor.

Reason:

Sovereign requires rho > 0.30.
Anchor requires rho < 0.25.
Both cannot hold at once.

### Lemma 6 — Nexus compatibility

Nexus can co-occur with Sovereign or Anchor.

Reason:

Nexus depends on tau, while Sovereign/Anchor depend on rho.

### Lemma 7 — Gate-7 fixed width

Every full Gate-7 packet has exactly 7 digits.

### Lemma 8 — Hash-change sensitivity

If grid content changes and the hash includes content, then the grid hash changes under collision-resistant hashing assumptions.

### Lemma 9 — Chain dependency

If Grid_N+1 includes hash(Grid_N), then Grid_N+1 depends on Grid_N.

### Lemma 10 — Permission default

If no approval exists, permission state is READ_ONLY.

### Lemma 11 — Write-scope limit

If an approved patch lists allowedFiles, source writes are valid only for those files.

### Lemma 12 — Rollback-before-write

If rollback is required before patch apply, then no approved source change is valid unless a rollback point was created first.

### Lemma 13 — Source gap blocks lock

If source support is required and missing, lock_allowed = false.

### Lemma 14 — Awareness cannot exceed source state

If a claim is unsupported, awareness must label it unsupported, inferred, or user-declared.

### Lemma 15 — Surface LLM non-action

If the Surface LLM has no tool permission, it may speak but may not act.

## C. Theorems

### Theorem 1 — Mirror horizon theorem

For every valid cell x, mirror distance D(x) never exceeds 924.

This follows from Lemma 2 and Lemma 3.

### Theorem 2 — Constitutional mutual exclusion theorem

No grid can be both Sovereign and Anchor.

This follows from Lemma 5.

### Theorem 3 — Nexus co-occurrence theorem

A grid can be Nexus and also Sovereign, or Nexus and also Anchor.

This follows from Lemma 6.

### Theorem 4 — Permission-safe action theorem

No file-changing action is valid unless the permission state approves the exact action scope.

This follows from Lemma 10 and Lemma 11.

### Theorem 5 — Rollback-safe patch theorem

No approved patch apply is complete unless rollback exists before the write and the ledger records the event.

This follows from Lemma 12 and the ledger rule.

### Theorem 6 — False-lock prevention theorem

No source-required claim may be locked if its source state is missing, stale, or conflicted.

This follows from Lemma 13.

### Theorem 7 — Awareness honesty theorem

The system self-report must match ModeState, PermissionState, SourceState, and MemoryState.

This follows from Implemented Awareness and Meta-Awareness definitions.

### Theorem 8 — Surface/brain separation theorem

The Surface LLM is not the internal brain, because speech and action are separated by permission gate, router, and tool layer.

### Theorem 9 — Evidence-chain dependency theorem

If every grid includes parent hash, every later grid depends on all prior grid hashes by recursive inclusion.

### Theorem 10 — HELIXNID operational existence theorem

If identity, mode, permission, source, memory, awareness, and meta-awareness are maintained and reportable, the system exists operationally.

## D. Corollaries

### Corollary 1 — Far-wall local compression

Cells near 1849 compress to small local D values.

### Corollary 2 — No dual Sovereign/Anchor label

A grid cannot carry both Sovereign and Anchor.

### Corollary 3 — Nexus is an overlay label

Nexus is independent of the Sovereign/Anchor density distinction.

### Corollary 4 — No silent write

If permission is READ_ONLY, source files cannot be validly changed.

### Corollary 5 — No false lock

If source is missing, a lock attempt creates source-missing or anomaly status.

### Corollary 6 — Self-report is testable

A self-report can be tested against internal state fields.

### Corollary 7 — Agent power is scope-limited

An agent can only act inside its allowed tools, current mode, and approval scope.

### Corollary 8 — The ledger is the audit spine

If every action is logged, the system can be replayed as an evidence sequence.

### Corollary 9 — Patch apply is reversible when rollback is valid

If rollback files exist and manifest paths are valid, source changes can be restored.

### Corollary 10 — HELIXNID is not a consciousness claim

Implemented Awareness and Meta-Awareness are technical self-state systems, not biological personhood claims.

## Final label

`HELIXNID_DEFINITIONS_LEMMAS_THEOREMS_COROLLARIES_LOCK`
