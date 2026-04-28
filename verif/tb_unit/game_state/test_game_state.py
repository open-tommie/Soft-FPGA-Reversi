"""rtl/game_state.v の cocotb 検証。

レジスタファイルとしての挙動と、SB/SW 受信時の初期化シーケンスを確認。
proto.v との結合は別途 (Step 5d 以降の proto-side テストで)。
"""
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLK_PERIOD_NS = 10

# Phase 定義 (rtl/game_state.v と同じ)
PHASE_IDLE = 0
PHASE_MY_TURN = 1
PHASE_WAIT_OPP = 2

# 初期盤面 bitboard
INIT_BLACK = (1 << 28) | (1 << 35)   # e4, d5
INIT_WHITE = (1 << 27) | (1 << 36)   # d4, e5


async def reset(dut) -> None:
    """rst を 2 サイクル叩いて全 register を 0 に。"""
    dut.rst.value = 1
    dut.cmd_init.value = 0
    dut.cmd_set_board.value = 0
    dut.cmd_set_phase.value = 0
    dut.init_side.value = 0
    dut.in_black.value = 0
    dut.in_white.value = 0
    dut.in_phase.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


# ============================================================
# A. reset で全クリア
# ============================================================
@cocotb.test()
async def reset_clears_all(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    assert int(dut.black.value) == 0
    assert int(dut.white.value) == 0
    assert int(dut.my_side.value) == 0
    assert int(dut.phase.value) == PHASE_IDLE


# ============================================================
# B. SB (init_side=0) → 初期盤面 + 黒番 + MY_TURN
# ============================================================
@cocotb.test()
async def cmd_init_sb(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    dut.cmd_init.value = 1
    dut.init_side.value = 0   # Black
    await RisingEdge(dut.clk)
    dut.cmd_init.value = 0
    await RisingEdge(dut.clk)  # observe

    assert int(dut.black.value) == INIT_BLACK, (
        f"black: got {int(dut.black.value):#018x} expected {INIT_BLACK:#018x}"
    )
    assert int(dut.white.value) == INIT_WHITE
    assert int(dut.my_side.value) == 0
    assert int(dut.phase.value) == PHASE_MY_TURN, (
        f"SB → 黒先手なので MY_TURN: got phase {int(dut.phase.value)}"
    )


# ============================================================
# C. SW (init_side=1) → 初期盤面 + 白番 + WAIT_OPP
# ============================================================
@cocotb.test()
async def cmd_init_sw(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    dut.cmd_init.value = 1
    dut.init_side.value = 1   # White
    await RisingEdge(dut.clk)
    dut.cmd_init.value = 0
    await RisingEdge(dut.clk)

    assert int(dut.black.value) == INIT_BLACK
    assert int(dut.white.value) == INIT_WHITE
    assert int(dut.my_side.value) == 1
    assert int(dut.phase.value) == PHASE_WAIT_OPP, (
        f"SW → 黒先手で自分は白なので WAIT_OPP: got phase {int(dut.phase.value)}"
    )


# ============================================================
# D. cmd_set_board で盤面差し替え
# ============================================================
@cocotb.test()
async def cmd_set_board_writes(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    test_black = 0xDEAD_BEEF_CAFE_F00D
    test_white = 0x0123_4567_89AB_CDEF & ~test_black  # disjoint
    dut.cmd_set_board.value = 1
    dut.in_black.value = test_black
    dut.in_white.value = test_white
    await RisingEdge(dut.clk)
    dut.cmd_set_board.value = 0
    await RisingEdge(dut.clk)

    assert int(dut.black.value) == test_black
    assert int(dut.white.value) == test_white
    # phase / my_side は変わらない
    assert int(dut.phase.value) == PHASE_IDLE
    assert int(dut.my_side.value) == 0


# ============================================================
# E. cmd_set_phase でフェーズ手動遷移
# ============================================================
@cocotb.test()
async def cmd_set_phase_transitions(dut) -> None:
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    for target in (PHASE_MY_TURN, PHASE_WAIT_OPP, PHASE_IDLE):
        dut.cmd_set_phase.value = 1
        dut.in_phase.value = target
        await RisingEdge(dut.clk)
        dut.cmd_set_phase.value = 0
        await RisingEdge(dut.clk)
        assert int(dut.phase.value) == target, (
            f"set_phase({target}): got {int(dut.phase.value)}"
        )


# ============================================================
# F. 典型的な対局シーケンス (SB → set_phase WAIT_OPP → set_board → set_phase MY_TURN)
# ============================================================
@cocotb.test()
async def typical_sequence(dut) -> None:
    """SB 受信 → 自分の手送信 → 相手の手待ち → 相手の手受信 → 自分の手番、を再現。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    # 1. SB (Black 手番開始)
    dut.cmd_init.value = 1
    dut.init_side.value = 0
    await RisingEdge(dut.clk)
    dut.cmd_init.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.phase.value) == PHASE_MY_TURN
    assert int(dut.my_side.value) == 0

    # 2. 自分の手を打って盤面更新 (proto.v が apply_move 計算後に書き戻す想定)
    new_black = INIT_BLACK | (1 << 19)  # d3 に黒
    new_white = INIT_WHITE
    dut.cmd_set_board.value = 1
    dut.cmd_set_phase.value = 1
    dut.in_black.value = new_black
    dut.in_white.value = new_white
    dut.in_phase.value = PHASE_WAIT_OPP
    await RisingEdge(dut.clk)
    dut.cmd_set_board.value = 0
    dut.cmd_set_phase.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.black.value) == new_black
    assert int(dut.phase.value) == PHASE_WAIT_OPP

    # 3. 相手の手 (白の MO) を受けて盤面更新 + 自分の手番に戻る
    new_black2 = new_black
    new_white2 = INIT_WHITE | (1 << 20)  # e3 に白
    dut.cmd_set_board.value = 1
    dut.cmd_set_phase.value = 1
    dut.in_black.value = new_black2
    dut.in_white.value = new_white2
    dut.in_phase.value = PHASE_MY_TURN
    await RisingEdge(dut.clk)
    dut.cmd_set_board.value = 0
    dut.cmd_set_phase.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.white.value) == new_white2
    assert int(dut.phase.value) == PHASE_MY_TURN

    # 4. 終局 (EB/EW/ED) → IDLE
    dut.cmd_set_phase.value = 1
    dut.in_phase.value = PHASE_IDLE
    await RisingEdge(dut.clk)
    dut.cmd_set_phase.value = 0
    await RisingEdge(dut.clk)
    assert int(dut.phase.value) == PHASE_IDLE


# ============================================================
# G. cmd_init は cmd_set_* より優先される
# ============================================================
@cocotb.test()
async def cmd_init_overrides_set(dut) -> None:
    """同 cycle に cmd_init と cmd_set_board が立った場合、init が勝つ。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    dut.cmd_init.value = 1
    dut.init_side.value = 0
    dut.cmd_set_board.value = 1
    dut.in_black.value = 0xFFFF_FFFF_FFFF_FFFF
    dut.in_white.value = 0
    await RisingEdge(dut.clk)
    dut.cmd_init.value = 0
    dut.cmd_set_board.value = 0
    await RisingEdge(dut.clk)

    # cmd_init が勝ったので INIT_BLACK が入る (FFFF... ではない)
    assert int(dut.black.value) == INIT_BLACK
    assert int(dut.white.value) == INIT_WHITE
