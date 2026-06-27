#!/usr/bin/env python3
"""HELIXNID core invariant tests.

Run:
    python3 HELIXNID_SYSTEM_ARCHIVE/tests/helixnid_core_tests.py
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import floor, log, pi

GRID_SIDE = 43
GRID_CELLS = 1849
OMEGA = 13507
N_V = 4_370_125
V_HELIX_TEXT = "0.01343747707793118"
KAPPA = 1.584962500721156
DELTA = 0.584962500721156
CHAOS_LEAK = 0.0283324170499
EULER_GAMMA = 0.5772156649


def mirror_d(x: int) -> int:
    return min(x, GRID_CELLS - x)


def even_anchor(x: int) -> int:
    if x in (1847, 1848):
        return 1848
    return x


def grid_hash(payload: str, parent_hash: str = "GENESIS") -> str:
    return sha256((parent_hash + "|" + payload).encode("utf-8")).hexdigest()


def constitutional_labels(rho: float, tau: int) -> set[str]:
    labels = {"BaseGrid"}
    if rho > 0.30:
        labels.add("Sovereign")
    if rho < 0.25:
        labels.add("Anchor")
    if tau > 450:
        labels.add("Nexus")
    return labels


@dataclass
class PermissionState:
    current_permission: str = "READ_ONLY"
    can_read: bool = True
    can_write: bool = False
    can_run_command: bool = False
    can_git_push: bool = False


@dataclass
class AwarenessState:
    current_mode: str
    permission_state: str
    source_state: str
    uncertainty_state: str


@dataclass
class MetaAwarenessState:
    awareness_complete: bool
    awareness_permission_safe: bool
    awareness_source_safe: bool
    self_model_update_needed: bool


def test_grid_cells() -> None:
    assert GRID_SIDE * GRID_SIDE == GRID_CELLS == 1849


def test_mirror_distance_examples() -> None:
    assert mirror_d(5) == 5
    assert mirror_d(1844) == 5
    assert mirror_d(20) == 20
    assert mirror_d(1829) == 20


def test_horizon_bound() -> None:
    assert floor(GRID_CELLS / 2) == 924
    for x in range(GRID_CELLS):
        assert mirror_d(x) <= 924


def test_even_anchor_lock() -> None:
    assert even_anchor(1847) == 1848
    assert even_anchor(1848) == 1848


def test_constitutional_exclusion_and_overlay() -> None:
    sovereign = constitutional_labels(0.31, 451)
    anchor = constitutional_labels(0.24, 451)
    assert "Sovereign" in sovereign
    assert "Anchor" not in sovereign
    assert "Nexus" in sovereign
    assert "Anchor" in anchor
    assert "Sovereign" not in anchor
    assert "Nexus" in anchor


def test_grid_hash_dependency() -> None:
    h0 = grid_hash("grid0")
    h1 = grid_hash("grid1", h0)
    h1_changed_parent = grid_hash("grid1", "DIFFERENT")
    assert h1 != h1_changed_parent


def test_v_helix_constant_close_to_locked_text() -> None:
    computed = pi / (log(N_V) ** 2)
    locked = float(V_HELIX_TEXT)
    assert abs(computed - locked) < 1e-6


def test_permission_default_blocks_write() -> None:
    p = PermissionState()
    assert p.current_permission == "READ_ONLY"
    assert p.can_read is True
    assert p.can_write is False
    assert p.can_run_command is False
    assert p.can_git_push is False


def test_awareness_meta_awareness() -> None:
    a = AwarenessState(
        current_mode="READ_ONLY",
        permission_state="READ_ONLY",
        source_state="PROJECT_NOT_LOADED",
        uncertainty_state="LOW",
    )
    m = MetaAwarenessState(
        awareness_complete=True,
        awareness_permission_safe=True,
        awareness_source_safe=True,
        self_model_update_needed=False,
    )
    assert a.current_mode == "READ_ONLY"
    assert m.awareness_permission_safe is True


def run_all() -> None:
    tests = [
        test_grid_cells,
        test_mirror_distance_examples,
        test_horizon_bound,
        test_even_anchor_lock,
        test_constitutional_exclusion_and_overlay,
        test_grid_hash_dependency,
        test_v_helix_constant_close_to_locked_text,
        test_permission_default_blocks_write,
        test_awareness_meta_awareness,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print("HELIXNID_CORE_TESTS_PASS")


if __name__ == "__main__":
    run_all()
