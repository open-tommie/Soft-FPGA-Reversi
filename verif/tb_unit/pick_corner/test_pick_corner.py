"""rtl/pick_corner.v の cocotb 検証。

1. 角が 1 つ合法手にある → その角が選ばれる
2. 角が複数合法手にある → 行優先（最小 bit index）の角が選ばれる
3. 角が合法手にない     → pick_lsb と同じ手（最小 bit index）が選ばれる
4. 合法手なし           → valid=0
5. ランダム fuzz        → Python golden と一致
"""
from __future__ import annotations

import random

import cocotb
from cocotb.triggers import Timer

CORNER_MASK = 0x8100_0000_0000_0081  # a1=0, h1=7, a8=56, h8=63


def py_pick_lsb(x: int) -> tuple[bool, int, int]:
    x &= (1 << 64) - 1
    if x == 0:
        return False, 0, 0
    one_hot = x & ((-x) & ((1 << 64) - 1))
    index = one_hot.bit_length() - 1
    return True, index, one_hot


def py_pick_corner(legal: int) -> tuple[bool, int, int]:
    corner_moves = legal & CORNER_MASK
    candidates = corner_moves if corner_moves else legal
    return py_pick_lsb(candidates)


async def settle(dut) -> None:
    await Timer(1, unit="ns")


async def drive(dut, val: int) -> tuple[bool, int, int]:
    dut.in_bits.value = val
    await settle(dut)
    return (
        bool(int(dut.valid.value)),
        int(dut.index.value),
        int(dut.one_hot.value),
    )


# ============================================================
# A. 合法手なし
# ============================================================
@cocotb.test()
async def no_legal_moves(dut) -> None:
    valid, index, one_hot = await drive(dut, 0)
    assert valid is False
    assert index == 0
    assert one_hot == 0


# ============================================================
# B. 各角単独
# ============================================================
@cocotb.test()
async def each_corner_single(dut) -> None:
    for bit in (0, 7, 56, 63):
        legal = 1 << bit
        valid, index, one_hot = await drive(dut, legal)
        assert valid is True, f"corner bit={bit}: valid should be True"
        assert index == bit, f"corner bit={bit}: got index={index}"
        assert one_hot == legal, f"corner bit={bit}: got one_hot={one_hot:#x}"


# ============================================================
# C. 角が複数 → 最小 index の角が選ばれる
# ============================================================
@cocotb.test()
async def multiple_corners_lowest_wins(dut) -> None:
    # a1(0) + h8(63) → a1 が選ばれる
    legal = (1 << 0) | (1 << 63)
    valid, index, _ = await drive(dut, legal)
    assert valid is True
    assert index == 0, f"a1+h8: expected index=0, got {index}"

    # h1(7) + a8(56) → h1 が選ばれる
    legal = (1 << 7) | (1 << 56)
    valid, index, _ = await drive(dut, legal)
    assert index == 7, f"h1+a8: expected index=7, got {index}"

    # 全 4 角 → a1(0) が選ばれる
    legal = CORNER_MASK
    valid, index, _ = await drive(dut, legal)
    assert index == 0, f"all corners: expected index=0, got {index}"


# ============================================================
# D. 角なし → pick_lsb と同じ結果
# ============================================================
@cocotb.test()
async def no_corner_falls_back_to_lsb(dut) -> None:
    # 角を含まない手のみ
    non_corner = ((1 << 64) - 1) & ~CORNER_MASK
    rng = random.Random(0xABCD)
    for _ in range(500):
        legal = rng.getrandbits(64) & non_corner
        if legal == 0:
            continue
        valid, index, one_hot = await drive(dut, legal)
        exp_valid, exp_index, exp_one_hot = py_pick_lsb(legal)
        assert valid == exp_valid
        assert index == exp_index, f"fallback: got {index}, expected {exp_index} ({legal:#x})"
        assert one_hot == exp_one_hot


# ============================================================
# E. ランダム fuzz
# ============================================================
@cocotb.test()
async def random_fuzz(dut) -> None:
    rng = random.Random(0xDEADBEEF)
    for i in range(10_000):
        legal = rng.getrandbits(64)
        valid, index, one_hot = await drive(dut, legal)
        exp_valid, exp_index, exp_one_hot = py_pick_corner(legal)
        if valid != exp_valid or index != exp_index or one_hot != exp_one_hot:
            raise AssertionError(
                f"fuzz #{i}: legal={legal:#018x}\n"
                f"  expected: valid={exp_valid} index={exp_index} one_hot={exp_one_hot:#018x}\n"
                f"  got:      valid={valid} index={index} one_hot={one_hot:#018x}"
            )
