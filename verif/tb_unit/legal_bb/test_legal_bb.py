"""rtl/legal_bb.v の cocotb 全方位検証。

verif/golden/reversi_rules.py を唯一の golden として、5 カテゴリの
テストを Verilator backend で回す:

  A. initial_position           初期局面 (黒番 / 白番)
  B. self_play_game             ランダム合法手で 1 ゲーム指して各局面確認
  C. extreme_cases              空盤、自分のみ、対角線のみ等の極端ケース
  D. random_fuzz                seed 固定でランダム盤面 10,000 件
  E. corner_pieces              全 4 隅に 1 駒置いた状態で 1 手読み

合計 ~10,070 件 の局面を bit-exact 比較。total ~5-15 秒で完走想定。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

# verif/ を import path に通して `from golden.reversi_rules import ...` できるように。
# 本ファイルは verif/tb_unit/legal_bb/test_legal_bb.py なので parents[2] が verif/。
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from golden.reversi_rules import (  # noqa: E402
    BLACK,
    WHITE,
    apply_move,
    init_board,
    legal_moves,
)


def board_to_bb(board: list[list[int]], target: int) -> int:
    """8x8 配列の target 色 (BLACK/WHITE) を 64bit bitboard へ。"""
    bits = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                bits |= 1 << (r * 8 + c)
    return bits


def bb_to_board(black_bb: int, white_bb: int) -> list[list[int]]:
    """2 つの bitboard を 8x8 配列へ復元。重複時は black 優先。"""
    board = [[0] * 8 for _ in range(8)]
    for i in range(64):
        bit = 1 << i
        r, c = i // 8, i % 8
        if black_bb & bit:
            board[r][c] = BLACK
        elif white_bb & bit:
            board[r][c] = WHITE
    return board


def legal_to_bb(moves: list[tuple[int, int]]) -> int:
    bits = 0
    for r, c in moves:
        bits |= 1 << (r * 8 + c)
    return bits


async def check(dut, black_bb: int, white_bb: int, side: int, label: str = "") -> None:
    """1 局面を DUT に投入して golden と一致確認。"""
    color = BLACK if side == 0 else WHITE
    board = bb_to_board(black_bb, white_bb)
    expected = legal_to_bb(legal_moves(board, color))

    dut.black.value = black_bb
    dut.white.value = white_bb
    dut.side.value = side
    await Timer(1, "ns")  # 純粋組合せなので 1 ns 待つだけで settle
    got = int(dut.legal.value)

    if got != expected:
        diff = got ^ expected
        raise AssertionError(
            f"{label}\n"
            f"  black   = {black_bb:#018x}\n"
            f"  white   = {white_bb:#018x}\n"
            f"  side    = {side} ({'WHITE' if side else 'BLACK'})\n"
            f"  expected= {expected:#018x}\n"
            f"  got     = {got:#018x}\n"
            f"  diff    = {diff:#018x}"
        )


# ============================================================
# A. 初期局面
# ============================================================
@cocotb.test()
async def initial_position(dut) -> None:
    """4 駒だけ置いた初期局面で黒番 / 白番ともに合法手 4 つ。"""
    board = init_board()
    black_bb = board_to_bb(board, BLACK)
    white_bb = board_to_bb(board, WHITE)
    await check(dut, black_bb, white_bb, 0, label="initial / black to move")
    await check(dut, black_bb, white_bb, 1, label="initial / white to move")


# ============================================================
# B. 自己対戦
# ============================================================
@cocotb.test()
async def self_play_game(dut) -> None:
    """ランダム合法手で 1 ゲーム終了まで指して各手番で legal_moves が一致。"""
    rng = random.Random(0xBEEF)
    board = init_board()
    side_color = BLACK
    consecutive_pass = 0
    plies = 0
    while plies < 80 and consecutive_pass < 2:
        plies += 1
        black_bb = board_to_bb(board, BLACK)
        white_bb = board_to_bb(board, WHITE)
        side_bit = 0 if side_color == BLACK else 1

        await check(
            dut,
            black_bb,
            white_bb,
            side_bit,
            label=f"self-play ply {plies} side={side_color}",
        )

        legal = legal_moves(board, side_color)
        if legal:
            move = rng.choice(legal)
            apply_move(board, move[0], move[1], side_color)
            consecutive_pass = 0
        else:
            consecutive_pass += 1
        side_color = WHITE if side_color == BLACK else BLACK


# ============================================================
# C. 極端ケース
# ============================================================
@cocotb.test()
async def extreme_cases(dut) -> None:
    """空盤、自分だけ、敵だけ、満杯等の corner case。"""
    full = (1 << 64) - 1

    # 空盤 → 合法手 0
    await check(dut, 0, 0, 0, label="empty board, black")
    await check(dut, 0, 0, 1, label="empty board, white")

    # 自分の駒だけ (敵駒なし) → 合法手 0
    await check(dut, full, 0, 0, label="all black, black to move")
    await check(dut, 0, full, 1, label="all white, white to move")

    # 敵の駒だけ (自分なし) → 合法手 0
    await check(dut, full, 0, 1, label="all black, white to move (no own)")
    await check(dut, 0, full, 0, label="all white, black to move (no own)")

    # 盤面満杯 (空 0) → 合法手 0
    await check(dut, full ^ (full >> 1), full >> 1, 0, label="full board (alternating)")

    # コーナー単体: a1 だけ自分、b1 が敵、c1 が空 → c1 が合法
    # bit_index: a1=0, b1=1, c1=2
    await check(dut, 1 << 0, 1 << 1, 0, label="a1=B b1=W → c1 expected legal")

    # 対角線のみ: a1〜h8 に黒、それ以外空 → 各駒の隣接が空、敵無いので 0
    diag = sum(1 << (i * 9) for i in range(8))
    await check(dut, diag, 0, 0, label="diagonal only")


# ============================================================
# D. ランダム fuzz
# ============================================================
@cocotb.test()
async def random_fuzz_10k(dut) -> None:
    """seed 固定で 10,000 件、bit-exact 比較。"""
    rng = random.Random(0xCAFEBEEF)
    n = 10_000
    for i in range(n):
        black_bb = rng.getrandbits(64)
        white_bb = rng.getrandbits(64) & ~black_bb  # 黒白 disjoint 保証
        side = rng.randrange(2)
        await check(dut, black_bb, white_bb, side, label=f"fuzz #{i}")


# ============================================================
# E. 4 隅 1 駒
# ============================================================
@cocotb.test()
async def corner_pieces(dut) -> None:
    """4 隅 (a1/h1/a8/h8) それぞれに 1 駒置いた状態で挙動確認。"""
    corners = {
        "a1": 0,
        "h1": 7,
        "a8": 56,
        "h8": 63,
    }
    for name, bit in corners.items():
        for side in (0, 1):
            # 自分のみ corner、敵なし → 合法手 0
            await check(dut, 1 << bit, 0, side,
                        label=f"corner {name} self only side={side}")
            # 敵のみ corner、自分なし → 合法手 0
            await check(dut, 0, 1 << bit, side,
                        label=f"corner {name} opp only side={side}")
