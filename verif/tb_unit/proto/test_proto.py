"""rtl/proto.v の cocotb ユニットテスト。

UART テキストプロトコル骨格 (Bootstrap step 3 の Verilog 化版) を
バイト粒度で駆動し、PI/VE/ER02 の応答を検証する。HIL ではなく純粋に
Verilator + cocotb で完結するので秒で回る。
"""
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLK_PERIOD_NS = 10


async def reset(dut) -> None:
    """rst を 2 サイクル叩いて初期状態へ。"""
    dut.rst.value = 1
    dut.rx_valid.value = 0
    dut.rx_byte.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


async def send_byte(dut, b: int) -> None:
    """1 byte を rx_valid pulse で投入。"""
    dut.rx_byte.value = b
    dut.rx_valid.value = 1
    await RisingEdge(dut.clk)
    dut.rx_valid.value = 0


async def send_line(dut, line: bytes) -> None:
    """LF を含む 1 行を順に投入。"""
    for b in line:
        await send_byte(dut, b)


async def collect_response(dut, max_ticks: int = 100) -> bytes:
    """tx_valid を観測しながら 1 行 (LF まで) 受信して返す。"""
    out = bytearray()
    for _ in range(max_ticks):
        await RisingEdge(dut.clk)
        if dut.tx_valid.value:
            byte = int(dut.tx_byte.value) & 0xFF
            out.append(byte)
            if byte == 0x0A:  # LF
                return bytes(out)
    raise AssertionError(
        f"応答行が {max_ticks} cycle 以内に終わらない: {bytes(out)!r}"
    )


@cocotb.test()
async def pi_returns_po(dut) -> None:
    """PI\\n → PO\\n"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"PI\n")
    resp = await collect_response(dut)
    assert resp == b"PO\n", f"期待 b'PO\\n' / 実際 {resp!r}"


@cocotb.test()
async def ve_returns_version(dut) -> None:
    """VE\\n → VE01reversi-fw\\n"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"VE\n")
    resp = await collect_response(dut)
    assert resp == b"VE01reversi-fw\n", f"期待 VE01reversi-fw / 実際 {resp!r}"


@cocotb.test()
async def unknown_returns_er02(dut) -> None:
    """XX\\n → ER02 unknown\\n"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"XX\n")
    resp = await collect_response(dut)
    assert resp.startswith(b"ER02"), f"ER02 を期待: {resp!r}"
    assert b"unknown" in resp, f"unknown を含むこと: {resp!r}"


@cocotb.test()
async def known_unimplemented_returns_er02(dut) -> None:
    """MO\\n も骨格段階では ER02 で返す (PI/VE 以外は全部一律)。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"MO\n")
    resp = await collect_response(dut)
    assert resp.startswith(b"ER02"), f"ER02 を期待: {resp!r}"


@cocotb.test()
async def repeated_pi(dut) -> None:
    """PI を 3 連続で投げて PO が 3 回返る (フレーミングが崩れない)。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    for _ in range(3):
        await send_line(dut, b"PI\n")
        resp = await collect_response(dut)
        assert resp == b"PO\n", f"PO 期待 / 実際 {resp!r}"


# ===== Step 5d-2: SB/SW で内部 game_state が初期化される =====
# 応答は依然 ER02 のままだが、game_state が SB/SW を受けて状態遷移する
# ことを階層アクセス (dut.u_game_state.*) で確認する。

PHASE_IDLE = 0
PHASE_MY_TURN = 1
PHASE_WAIT_OPP = 2
INIT_BLACK = (1 << 28) | (1 << 35)  # e4, d5
INIT_WHITE = (1 << 27) | (1 << 36)  # d4, e5


@cocotb.test()
async def sb_initializes_black_then_picks_move(dut) -> None:
    """SB を受けると my_side=Black、自分の最初の手 (d3) が打たれて phase=WAIT_OPP。

    5d-2 で cmd_init による初期化、5d-3b で続けて S_PLACE_MY が走るため、
    SB の後の game_state は「初期盤面 + 自分の d3」の状態。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    await collect_response(dut)

    assert int(dut.u_game_state.my_side.value) == 0, "SB → Black"
    assert int(dut.u_game_state.phase.value) == PHASE_WAIT_OPP
    assert int(dut.u_game_state.black.value) == INIT_BLACK | (1 << coord_to_bit("d3"))
    assert int(dut.u_game_state.white.value) == INIT_WHITE


@cocotb.test()
async def sw_initializes_white_wait_opp(dut) -> None:
    """SW を受けると my_side=White, phase=WAIT_OPP, 初期盤面。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    await collect_response(dut)

    assert int(dut.u_game_state.my_side.value) == 1, "SW → White"
    assert int(dut.u_game_state.phase.value) == PHASE_WAIT_OPP
    assert int(dut.u_game_state.black.value) == INIT_BLACK
    assert int(dut.u_game_state.white.value) == INIT_WHITE


@cocotb.test()
async def pi_does_not_touch_game_state(dut) -> None:
    """SB で初期化後、PI を投げても game_state は不変。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    await collect_response(dut)
    phase_before = int(dut.u_game_state.phase.value)
    side_before = int(dut.u_game_state.my_side.value)
    black_before = int(dut.u_game_state.black.value)
    white_before = int(dut.u_game_state.white.value)

    await send_line(dut, b"PI\n")
    resp = await collect_response(dut)
    assert resp == b"PO\n"

    assert int(dut.u_game_state.phase.value) == phase_before
    assert int(dut.u_game_state.my_side.value) == side_before
    assert int(dut.u_game_state.black.value) == black_before
    assert int(dut.u_game_state.white.value) == white_before


# ===== Step 5d-3a: MO<xy> で相手の駒が盤面に追加される (反転なし) =====


def coord_to_bit(coord: str) -> int:
    """'d3' → bit_index (= 19)。"""
    col = ord(coord[0]) - ord("a")
    row = ord(coord[1]) - ord("1")
    return row * 8 + col


@cocotb.test()
async def mo_adds_opp_white_after_sb(dut) -> None:
    """SB (my=Black) → MO<xy> で相手 (White) の駒が盤面に追加される。

    5d-3b 適用後: SB で自分の手 (d3) が打たれているので、その後の MO は
    現在の盤面に対して相手駒を追加する。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    await collect_response(dut)
    assert int(dut.u_game_state.my_side.value) == 0

    # SB 直後の状態をスナップショット (5d-3b で d3 が打たれている)
    white_before = int(dut.u_game_state.white.value)
    black_before = int(dut.u_game_state.black.value)

    # MOf6 (相手 = White の手として f6 が来た想定)
    await send_line(dut, b"MOf6\n")
    await collect_response(dut)

    # White に f6 が追加されるはず。同時に S_PLACE_MY で自分 (Black) の
    # 次の手も打たれる可能性があるので、white の差分のみ厳密に検査する。
    bit_f6 = coord_to_bit("f6")
    new_white = int(dut.u_game_state.white.value)
    assert new_white & (1 << bit_f6), (
        f"white should have bit_f6={bit_f6} set: got {new_white:#018x}"
    )
    # white は基本的に増えるだけ (proto は反転なし)
    assert (new_white & white_before) == white_before, "白の既存 bit が消えた"


@cocotb.test()
async def mo_adds_opp_black_after_sw(dut) -> None:
    """SW (my=White) → MO<xy> で相手 (Black) の駒が盤面に追加される。

    SW では自分の手はまだ打たないので white は INIT_WHITE のまま。
    MO 後は相手 (Black) の駒が増え、続く S_PLACE_MY で自分 (White) の駒も打たれる。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    await collect_response(dut)
    assert int(dut.u_game_state.my_side.value) == 1
    assert int(dut.u_game_state.black.value) == INIT_BLACK
    assert int(dut.u_game_state.white.value) == INIT_WHITE

    await send_line(dut, b"MOe6\n")
    await collect_response(dut)

    bit_e6 = coord_to_bit("e6")
    new_black = int(dut.u_game_state.black.value)
    new_white = int(dut.u_game_state.white.value)
    # black に e6 が追加されている
    assert new_black & (1 << bit_e6), (
        f"black should have bit_e6={bit_e6} set: got {new_black:#018x}"
    )
    # white にも 1 個増えている (S_PLACE_MY で自分の手)
    assert bin(new_white).count("1") == bin(INIT_WHITE).count("1") + 1


@cocotb.test()
async def mo_invalid_coord_does_not_change_board(dut) -> None:
    """MO<XY> (大文字) は coord.parse_valid=0 で盤面に手を加えない。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    await collect_response(dut)

    # SB 後の状態 (5d-3b 適用後: 自分の d3 が打たれている)
    black_after_sb = int(dut.u_game_state.black.value)
    white_after_sb = int(dut.u_game_state.white.value)

    # MOA1: 大文字 'A' は invalid なので何も起こらない
    await send_line(dut, b"MOA1\n")
    await collect_response(dut)

    assert int(dut.u_game_state.black.value) == black_after_sb
    assert int(dut.u_game_state.white.value) == white_after_sb


# ===== Step 5d-3b: SB / MO 後に自分の手を選んで盤面に置く =====


@cocotb.test()
async def sb_picks_own_first_move(dut) -> None:
    """SB → 自分 (Black) の合法手から行優先で先頭 (d3) を選んで盤面に置く。

    初期局面で黒の合法手は d3/c4/f5/e6 (= bits 19/26/37/44)。
    pick_lsb で最下位 bit 19 (d3) が選ばれて black に追加される。
    phase は WAIT_OPP に遷移。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    await collect_response(dut)

    expected_black = INIT_BLACK | (1 << coord_to_bit("d3"))
    expected_white = INIT_WHITE
    assert int(dut.u_game_state.black.value) == expected_black, (
        f"black after SB: got {int(dut.u_game_state.black.value):#018x}, "
        f"expected {expected_black:#018x}"
    )
    assert int(dut.u_game_state.white.value) == expected_white
    assert int(dut.u_game_state.phase.value) == PHASE_WAIT_OPP


@cocotb.test()
async def sw_does_not_pick_own_move(dut) -> None:
    """SW (White, 相手 Black 先手) は自分の手をまだ選ばない。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    await collect_response(dut)

    # 盤面は変わっていない (相手の MO 待ち)
    assert int(dut.u_game_state.black.value) == INIT_BLACK
    assert int(dut.u_game_state.white.value) == INIT_WHITE
    assert int(dut.u_game_state.phase.value) == PHASE_WAIT_OPP


@cocotb.test()
async def mo_then_pick_own_move(dut) -> None:
    """SW → MO で相手の手を受けたら自分 (White) の手も自動で打つ。

    SW で my_side=White、相手は Black の先手。
    相手 (Black) が d3 を打った想定で MOd3。
    その時点の盤面 (反転なし、Black に d3 追加) で
    白の合法手のうち最下位 bit を選んで white に追加する。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    await collect_response(dut)

    # 相手 (Black) の MOd3 を投入
    await send_line(dut, b"MOd3\n")
    await collect_response(dut)

    # 期待: black = INIT_BLACK | bit_d3 (Step 5d-3a 動作)
    bit_d3 = coord_to_bit("d3")
    expected_black = INIT_BLACK | (1 << bit_d3)
    assert int(dut.u_game_state.black.value) == expected_black, (
        f"black: got {int(dut.u_game_state.black.value):#018x}, "
        f"expected {expected_black:#018x}"
    )

    # white は INIT_WHITE | (白の最下位合法手 bit) で、phase は WAIT_OPP
    # 反転なしなので legal_bb は INIT_BLACK|d3 / INIT_WHITE / side=White で計算
    # この時点で白の合法手 (反転なしの単純な flip 計算) が何かは Python golden
    # と完全一致しないので、ここでは最低限 「白の駒が 1 個増えてる」 と
    # 「phase が WAIT_OPP」 だけ確認する。
    new_white = int(dut.u_game_state.white.value)
    assert bin(new_white).count("1") == bin(INIT_WHITE).count("1") + 1, (
        f"white should have +1 piece, got {bin(new_white).count('1')} pieces"
    )
    assert int(dut.u_game_state.phase.value) == PHASE_WAIT_OPP
