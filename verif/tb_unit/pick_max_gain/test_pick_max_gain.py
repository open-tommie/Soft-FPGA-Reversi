"""rtl/pick_max_gain.v の cocotb 検証。

着手後の自駒が最大になる合法手を選ぶことを検証:
  A. ゼロ入力で valid=0 / index=0 / one_hot=0
  B. 単独合法手はそのまま返す
  C. 初期局面の合法手から最大 gain を選ぶ
  D. 同 gain なら最小 index を返す
  E. ランダム fuzz (5,000 件) で Python 等価実装と一致
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from golden.reversi_rules import BLACK, WHITE, init_board, legal_moves  # noqa: E402

MASK64     = (1 << 64) - 1
MASK_NOT_A = 0xFEFEFEFEFEFEFEFE
MASK_NOT_H = 0x7F7F7F7F7F7F7F7F

_DIRS = [
    ( 1, MASK_NOT_A),
    (-1, MASK_NOT_H),
    ( 8, MASK64),
    (-8, MASK64),
    ( 9, MASK_NOT_A),
    ( 7, MASK_NOT_H),
    (-7, MASK_NOT_A),
    (-9, MASK_NOT_H),
]


def _shift(x: int, d: int, mask: int) -> int:
    return ((x << d) if d > 0 else (x >> -d)) & mask & MASK64


def py_flip_calc(own: int, opp: int, move_idx: int) -> int:
    """flip_calc.v の Python 等価実装。"""
    move = 1 << move_idx
    if (own | opp) & move:
        return 0
    total = 0
    for shift, mask in _DIRS:
        run = 0
        cur = _shift(move, shift, mask) & opp
        while cur:
            run |= cur
            cur = _shift(cur, shift, mask) & opp
        if _shift(run, shift, mask) & own:
            total |= run
    return total & MASK64


def py_pick_max_gain(own: int, opp: int, legal: int) -> tuple[bool, int, int]:
    """pick_max_gain.v の Python 等価実装。同 gain なら最小 index を選ぶ。"""
    legal &= MASK64
    if legal == 0:
        return False, 0, 0
    best_gain = -1
    best_idx  = 0
    for i in range(64):
        if legal & (1 << i):
            gain = bin(py_flip_calc(own, opp, i)).count("1")
            if gain > best_gain:
                best_gain = gain
                best_idx  = i
    return True, best_idx, 1 << best_idx


def board_to_bb(board: list, color: int) -> int:
    bb = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == color:
                bb |= 1 << (r * 8 + c)
    return bb


def moves_to_bb(moves: list) -> int:
    bb = 0
    for r, c in moves:
        bb |= 1 << (r * 8 + c)
    return bb


async def settle(dut) -> None:
    await Timer(1, unit="ns")


async def drive(dut, own: int, opp: int, legal: int) -> tuple[bool, int, int]:
    dut.own.value     = own
    dut.opp.value     = opp
    dut.in_bits.value = legal
    await settle(dut)
    return (
        bool(int(dut.valid.value)),
        int(dut.index.value),
        int(dut.one_hot.value),
    )


# ============================================================
# A. ゼロ入力
# ============================================================
@cocotb.test()
async def zero_input(dut) -> None:
    valid, index, one_hot = await drive(dut, 0, 0, 0)
    assert valid is False, f"valid expected False, got {valid}"
    assert index   == 0,   f"index expected 0, got {index}"
    assert one_hot == 0,   f"one_hot expected 0, got {one_hot:#x}"


# ============================================================
# B. 単独合法手はそのまま返す
# ============================================================
@cocotb.test()
async def single_legal_move(dut) -> None:
    """合法手が 1 つだけなら gain によらずその手を返す。"""
    for i in range(64):
        valid, index, one_hot = await drive(dut, 0, 0, 1 << i)
        assert valid is True,       f"bit {i}: valid expected True"
        assert index == i,          f"bit {i}: index got {index}"
        assert one_hot == (1 << i), f"bit {i}: one_hot got {one_hot:#x}"


# ============================================================
# C. 初期局面の合法手から最大 gain を選ぶ
# ============================================================
@cocotb.test()
async def initial_board_max_gain(dut) -> None:
    board = init_board()
    for color, opp_color in ((BLACK, WHITE), (WHITE, BLACK)):
        own_bb = board_to_bb(board, color)
        opp_bb = board_to_bb(board, opp_color)
        legal  = moves_to_bb(legal_moves(board, color))

        exp_valid, exp_idx, exp_one_hot = py_pick_max_gain(own_bb, opp_bb, legal)
        valid, index, one_hot = await drive(dut, own_bb, opp_bb, legal)

        label = "BLACK" if color == BLACK else "WHITE"
        assert valid == exp_valid,     f"{label}: valid mismatch"
        assert index == exp_idx,       f"{label}: index {index} != expected {exp_idx}"
        assert one_hot == exp_one_hot, f"{label}: one_hot mismatch"


# ============================================================
# D. 同 gain なら最小 index を返す
# ============================================================
@cocotb.test()
async def tie_picks_lowest_index(dut) -> None:
    """gain が同じ合法手が複数あるとき最小 index を選ぶ。"""
    # legal だが own/opp が空 → flip=0 で全手同 gain (0)
    # → 最小 index が選ばれるはず
    for bits in [0b011, 0b110, 0b101, (1 << 10) | (1 << 20) | (1 << 30)]:
        exp_valid, exp_idx, _ = py_pick_max_gain(0, 0, bits)
        valid, index, _       = await drive(dut, 0, 0, bits)
        assert valid == exp_valid
        assert index == exp_idx, f"bits={bits:#x}: index {index} != {exp_idx}"


# ============================================================
# E. ランダム fuzz
# ============================================================
@cocotb.test()
async def random_fuzz(dut) -> None:
    rng   = random.Random(0xDEADBEEF)
    n     = 5_000
    for trial in range(n):
        own   = rng.getrandbits(64) & MASK64
        opp   = rng.getrandbits(64) & ~own & MASK64
        empty = (~(own | opp)) & MASK64
        legal = empty & rng.getrandbits(64) & MASK64

        exp_valid, exp_idx, exp_one_hot = py_pick_max_gain(own, opp, legal)
        valid, index, one_hot           = await drive(dut, own, opp, legal)

        if valid != exp_valid or index != exp_idx or one_hot != exp_one_hot:
            raise AssertionError(
                f"fuzz #{trial}:\n"
                f"  own={own:#018x} opp={opp:#018x} legal={legal:#018x}\n"
                f"  expected: valid={exp_valid} index={exp_idx} one_hot={exp_one_hot:#018x}\n"
                f"  got:      valid={valid}      index={index}  one_hot={one_hot:#018x}"
            )
