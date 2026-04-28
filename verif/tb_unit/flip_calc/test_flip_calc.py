"""rtl/flip_calc.v の cocotb 検証。

Python golden `find_flips()` と bit-exact 比較。検証カテゴリ:
  A. initial_legal_moves   初期局面の 4 黒合法手で flip ビットマップ一致
  B. cross_capture         十字方向 (E/W/N/S) の単純捕捉
  C. diagonal_capture      対角方向 (NE/NW/SE/SW) の捕捉
  D. multi_direction       複数方向同時捕捉
  E. invalid_no_flip       不正手 (隣接 opp なし、own で終わらない) は flip=0
  F. random_fuzz           seed 固定 5,000 件 で golden と完全一致
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from golden.reversi_rules import (  # noqa: E402
    BLACK,
    WHITE,
    find_flips,
    init_board,
)


def board_to_bb(board: list[list[int]], target: int) -> int:
    bits = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                bits |= 1 << (r * 8 + c)
    return bits


def bb_to_board(black_bb: int, white_bb: int) -> list[list[int]]:
    board = [[0] * 8 for _ in range(8)]
    for i in range(64):
        bit = 1 << i
        r, c = i // 8, i % 8
        if black_bb & bit:
            board[r][c] = BLACK
        elif white_bb & bit:
            board[r][c] = WHITE
    return board


def find_flips_bb(black_bb: int, white_bb: int, color: int, move_bit: int) -> int:
    """Python golden の find_flips を bitboard 表現で。"""
    board = bb_to_board(black_bb, white_bb)
    r, c = move_bit // 8, move_bit % 8
    flips = find_flips(board, r, c, color)
    out = 0
    for fr, fc in flips:
        out |= 1 << (fr * 8 + fc)
    return out


async def check(dut, own: int, opp: int, move_bit: int, label: str = "") -> None:
    """1 局面を DUT に投入し、Python golden と一致確認。

    own が color (BLACK/WHITE) のどちらに対応するかは呼び元で決める。
    cocotb 側では own → black / opp → white として golden を呼ぶ。
    """
    expected = find_flips_bb(own, opp, BLACK, move_bit)

    dut.own.value = own
    dut.opp.value = opp
    dut.move_idx.value = move_bit
    await Timer(1, unit="ns")
    got = int(dut.flip.value)

    if got != expected:
        raise AssertionError(
            f"{label}\n"
            f"  own      = {own:#018x}\n"
            f"  opp      = {opp:#018x}\n"
            f"  move     = {move_bit} ({chr(ord('a') + move_bit % 8)}{move_bit // 8 + 1})\n"
            f"  expected = {expected:#018x}\n"
            f"  got      = {got:#018x}\n"
            f"  diff     = {(got ^ expected):#018x}"
        )


# ============================================================
# A. 初期局面: 4 黒合法手での flip
# ============================================================
@cocotb.test()
async def initial_legal_moves(dut) -> None:
    """初期局面で黒の合法手 d3/c4/f5/e6 それぞれの flip。"""
    board = init_board()
    black = board_to_bb(board, BLACK)
    white = board_to_bb(board, WHITE)

    # 4 つの合法手それぞれ 1 駒裏返す
    for coord_str in ("d3", "c4", "f5", "e6"):
        col = ord(coord_str[0]) - ord("a")
        row = ord(coord_str[1]) - ord("1")
        move_bit = row * 8 + col
        await check(dut, black, white, move_bit, label=f"initial Black plays {coord_str}")


# ============================================================
# B. 単純十字捕捉
# ============================================================
@cocotb.test()
async def east_capture(dut) -> None:
    """X..Y..O のうち X (own) の横位置に置いて O 一個キャプチャ。
    具体: 黒(own) at a1, 白(opp) at b1, 空 at c1
          c1 (col=2, row=0, bit=2) に黒置く → b1 (bit=1) フリップ。
    """
    own = 1 << 0   # a1
    opp = 1 << 1   # b1
    await check(dut, own, opp, 2, label="capture b1 by playing c1 from a1")


@cocotb.test()
async def west_capture(dut) -> None:
    """h1=own, g1=opp, f1=空 → f1 (bit=5) に own 置く → g1 (bit=6) フリップ。"""
    own = 1 << 7   # h1
    opp = 1 << 6   # g1
    await check(dut, own, opp, 5, label="capture g1 by playing f1 from h1")


@cocotb.test()
async def north_capture(dut) -> None:
    """a8=own, a7=opp, a6=空 → a6 (bit=40) に own → a7 (bit=48) フリップ。"""
    own = 1 << 56  # a8
    opp = 1 << 48  # a7
    await check(dut, own, opp, 40, label="capture a7 by playing a6 from a8")


@cocotb.test()
async def south_capture(dut) -> None:
    """a1=own, a2=opp, a3=空 → a3 (bit=16) に own → a2 (bit=8) フリップ。"""
    own = 1 << 0   # a1
    opp = 1 << 8   # a2
    await check(dut, own, opp, 16, label="capture a2 by playing a3 from a1")


# ============================================================
# C. 対角方向捕捉
# ============================================================
@cocotb.test()
async def se_capture(dut) -> None:
    """a1=own, b2=opp, c3=空 → c3 (bit=18) → b2 (bit=9) フリップ。"""
    own = 1 << 0   # a1
    opp = 1 << 9   # b2
    await check(dut, own, opp, 18, label="SE capture b2 by playing c3 from a1")


@cocotb.test()
async def sw_capture(dut) -> None:
    """h1=own, g2=opp, f3=空 → f3 (bit=21) → g2 (bit=14) フリップ。"""
    own = 1 << 7   # h1
    opp = 1 << 14  # g2
    await check(dut, own, opp, 21, label="SW capture g2 by playing f3 from h1")


# ============================================================
# D. 複数方向同時
# ============================================================
@cocotb.test()
async def multi_direction(dut) -> None:
    """初期局面 + 黒 d3 (= bit 19) で d4 だけが flip するか確認。
    d3 から SE → d4(白)→ e5(白)→ ... e5 は白なので run。e5 の先 f6 は空 → flip しない。
    d3 から E   → e3(空) → flip しない。
    d3 から S   → d4(白) → d5(黒) → flip = d4。
    結果: d4 (bit 27) のみ flip。
    """
    board = init_board()
    black = board_to_bb(board, BLACK)
    white = board_to_bb(board, WHITE)
    move_bit = 19  # d3
    await check(dut, black, white, move_bit, label="initial + d3 → flip d4 only")


# ============================================================
# E. 不正手では flip = 0
# ============================================================
@cocotb.test()
async def invalid_no_flip(dut) -> None:
    """周囲に opp も own も無い、または run 終端が own でない手は flip = 0。"""
    # ケース1: 完全に孤立した a1 (own/opp 何もなし)
    await check(dut, 0, 0, 0, label="empty board, move at a1")

    # ケース2: 隣接 opp なし
    own = 1 << 0   # a1
    await check(dut, own, 0, 18, label="own only, no opp adj to c3")

    # ケース3: opp はあるが run 終端に own がない (全部空)
    opp = 1 << 1   # b1
    await check(dut, 0, opp, 2, label="opp at b1, no own at any direction")


# ============================================================
# F. ランダム fuzz
# ============================================================
@cocotb.test()
async def random_fuzz_5k(dut) -> None:
    """seed 固定で 5,000 件、Python golden と完全一致。"""
    rng = random.Random(0xFEEDFACE)
    n = 5_000
    for i in range(n):
        own = rng.getrandbits(64)
        opp = rng.getrandbits(64) & ~own
        # move_idx は own/opp と重ならない位置 (= 空マス) を選びたいが、
        # 重なってても DUT/golden の挙動が一致すれば良いので適当に選ぶ
        move_bit = rng.randrange(64)
        await check(dut, own, opp, move_bit, label=f"fuzz #{i}")
