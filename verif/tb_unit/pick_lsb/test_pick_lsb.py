"""rtl/pick_lsb.v の cocotb 検証。

最下位 set bit 抽出が:
  1. ゼロ入力で valid=0 / index=0 / one_hot=0
  2. 単独 bit に対して bit position を返す
  3. 複数 bit のとき最下位を返す
  4. ランダム fuzz (10,000 件) で Python 等価実装と一致
  5. Python golden の `legal_moves()` 返却順 (行優先 a1, b1, ..., h8) と整合
     = legal_bb 出力に pick_lsb をかけた結果が legal_moves() の最初の要素
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

# verif/ を import path に通す
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from golden.reversi_rules import (  # noqa: E402
    BLACK,
    WHITE,
    init_board,
    legal_moves,
)


def py_pick_lsb(x: int) -> tuple[bool, int, int]:
    """golden 側の参照実装。x & -x のトリック。"""
    x &= (1 << 64) - 1
    if x == 0:
        return False, 0, 0
    one_hot = x & ((-x) & ((1 << 64) - 1))
    index = one_hot.bit_length() - 1
    return True, index, one_hot


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
# A. ゼロ入力
# ============================================================
@cocotb.test()
async def zero_input(dut) -> None:
    valid, index, one_hot = await drive(dut, 0)
    assert valid is False, f"valid expected False, got {valid}"
    assert index == 0, f"index expected 0, got {index}"
    assert one_hot == 0, f"one_hot expected 0, got {one_hot:#x}"


# ============================================================
# B. 各 bit 単独
# ============================================================
@cocotb.test()
async def each_single_bit(dut) -> None:
    for i in range(64):
        x = 1 << i
        valid, index, one_hot = await drive(dut, x)
        assert valid is True
        assert index == i, f"single bit {i}: got index {index}"
        assert one_hot == x, f"single bit {i}: got one_hot {one_hot:#x}"


# ============================================================
# C. 複数 bit で最下位が選ばれる
# ============================================================
@cocotb.test()
async def lowest_wins(dut) -> None:
    """各下位 bit i に対して、上位の bit が立っていても i が選ばれる。"""
    for i in range(63):
        # bit i + bit (i+1)
        x = (1 << i) | (1 << (i + 1))
        valid, index, _ = await drive(dut, x)
        assert valid is True
        assert index == i, f"i={i} + i+1: got index {index}, expected {i}"

    # 全 bit on → index = 0
    valid, index, _ = await drive(dut, (1 << 64) - 1)
    assert valid is True
    assert index == 0, f"all bits set: got index {index}"

    # 上位 bit のみ → index = 63
    valid, index, _ = await drive(dut, 1 << 63)
    assert index == 63


# ============================================================
# D. ランダム fuzz
# ============================================================
@cocotb.test()
async def random_fuzz(dut) -> None:
    rng = random.Random(0xDEADBEEF)
    n = 10_000
    for i in range(n):
        x = rng.getrandbits(64)
        valid, index, one_hot = await drive(dut, x)
        exp_valid, exp_index, exp_one_hot = py_pick_lsb(x)
        if valid != exp_valid or index != exp_index or one_hot != exp_one_hot:
            raise AssertionError(
                f"fuzz #{i}: x={x:#018x}\n"
                f"  expected: valid={exp_valid} index={exp_index} one_hot={exp_one_hot:#018x}\n"
                f"  got:      valid={valid} index={index} one_hot={one_hot:#018x}"
            )


# ============================================================
# E. legal_moves() の返却順と整合
# ============================================================
@cocotb.test()
async def matches_legal_moves_first(dut) -> None:
    """各局面で pick_lsb(legal bitboard) が legal_moves() の最初の要素と一致する。

    これが OK なら、proto.v が「行優先 a1, b1, ..., h8」の手選択順序を
    自然に守れる (Python golden と同じ手を返す)。
    """
    rng = random.Random(0xC0FFEE)

    def legal_to_bb(moves):
        bits = 0
        for r, c in moves:
            bits |= 1 << (r * 8 + c)
        return bits

    # 初期局面
    board = init_board()
    for color in (BLACK, WHITE):
        moves = legal_moves(board, color)
        if not moves:
            continue
        first_r, first_c = moves[0]
        expected_bit = first_r * 8 + first_c
        bb = legal_to_bb(moves)
        valid, index, _ = await drive(dut, bb)
        assert valid and index == expected_bit, (
            f"initial color={color}: legal_moves[0] = bit {expected_bit}, "
            f"pick_lsb gave {index}"
        )

    # ランダム盤面 1000 件
    for i in range(1000):
        # 黒/白 disjoint な 2 つの bitboard を作って board に変換
        black_bb = rng.getrandbits(64)
        white_bb = rng.getrandbits(64) & ~black_bb
        board = [[0] * 8 for _ in range(8)]
        for b in range(64):
            r, c = b // 8, b % 8
            if black_bb & (1 << b):
                board[r][c] = BLACK
            elif white_bb & (1 << b):
                board[r][c] = WHITE

        for color in (BLACK, WHITE):
            moves = legal_moves(board, color)
            if not moves:
                continue
            first_r, first_c = moves[0]
            expected_bit = first_r * 8 + first_c
            bb = legal_to_bb(moves)
            valid, index, _ = await drive(dut, bb)
            assert valid and index == expected_bit, (
                f"random #{i} color={color}: legal_moves[0] = bit {expected_bit}, "
                f"pick_lsb gave {index}"
            )
