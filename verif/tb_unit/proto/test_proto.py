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
    """SB → my_side=Black、自分の最初の手 (d3) が打たれて反転、phase=WAIT_OPP。

    Step 6 で flip_calc が結線済み:
      - 黒が d3 に置く → 縦方向で d4 (白) が挟まって反転 → 黒
      - 結果: black = INIT_BLACK | d3 | d4, white = INIT_WHITE & ~d4
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    # SB 後は MO + BS の 2 行
    await collect_response(dut)
    await collect_response(dut)

    bit_d3 = coord_to_bit("d3")
    bit_d4 = coord_to_bit("d4")
    expected_black = INIT_BLACK | (1 << bit_d3) | (1 << bit_d4)
    expected_white = INIT_WHITE & ~(1 << bit_d4)

    assert int(dut.u_game_state.my_side.value) == 0
    assert int(dut.u_game_state.phase.value) == PHASE_WAIT_OPP
    assert int(dut.u_game_state.black.value) == expected_black, (
        f"black: got {int(dut.u_game_state.black.value):#018x}, "
        f"expected {expected_black:#018x}"
    )
    assert int(dut.u_game_state.white.value) == expected_white, (
        f"white: got {int(dut.u_game_state.white.value):#018x}, "
        f"expected {expected_white:#018x}"
    )


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
    # SB 後は MO + BS の 2 行
    await collect_response(dut)
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
    # SB 後は MO + BS の 2 行
    await collect_response(dut)
    await collect_response(dut)
    assert int(dut.u_game_state.my_side.value) == 0

    # SB 直後の状態をスナップショット (5d-3b で d3 が打たれて d4 反転、Step 6)
    white_before = int(dut.u_game_state.white.value)
    black_before = int(dut.u_game_state.black.value)

    # MOf6 (相手 = White の手として f6 が来た想定)
    # 反転チェック: f6 から見て北方向 (e5=白, ...) には対角ライン (NW: e5白→d4黒)
    # SB 後の盤面で white は d4 反転済み = e5 のみ。f6 White を置いても反転は
    # 個別に flip_calc が決める。ここでは「white に f6 が追加され、black の数が
    # 減る (反転で黒→白) または不変」のいずれかを許容する。
    await send_line(dut, b"MOf6\n")
    await collect_response(dut)
    await collect_response(dut)

    bit_f6 = coord_to_bit("f6")
    new_white = int(dut.u_game_state.white.value)
    new_black = int(dut.u_game_state.black.value)
    # f6 自体は white に追加される
    assert new_white & (1 << bit_f6), (
        f"white should have bit_f6={bit_f6} set: got {new_white:#018x}"
    )
    # black + white の総数は (前の合計 + 1 = 相手の MO だけ) + my_move による +1 = 前 +2
    # 反転は black ↔ white のやり取りなので合計は変わらない
    assert bin(new_black).count("1") + bin(new_white).count("1") == \
        bin(black_before).count("1") + bin(white_before).count("1") + 2


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
async def sb_picks_own_first_move_with_flip(dut) -> None:
    """SB → 黒が d3 を選んで反転 (d4 が黒に)、phase=WAIT_OPP。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    await collect_response(dut)
    await collect_response(dut)

    bit_d3 = coord_to_bit("d3")
    bit_d4 = coord_to_bit("d4")
    expected_black = INIT_BLACK | (1 << bit_d3) | (1 << bit_d4)
    expected_white = INIT_WHITE & ~(1 << bit_d4)
    assert int(dut.u_game_state.black.value) == expected_black
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


# ===== Step 5d-3c: SB / MO 後の応答が "MO<xy>\n" になる =====


def bit_to_coord(bit: int) -> str:
    col = bit & 0x7
    row = (bit >> 3) & 0x7
    return f"{chr(ord('a') + col)}{chr(ord('1') + row)}"


@cocotb.test()
async def sb_responds_with_mo(dut) -> None:
    """SB → "MOd3\\n" が返る (黒の最下位合法手 d3 を打って通知)。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    resp = await collect_response(dut)
    assert resp == b"MOd3\n", f"期待 MOd3 / 実際 {resp!r}"


@cocotb.test()
async def mo_responds_with_mo(dut) -> None:
    """SW → MOd3 (相手 Black) → 自分 (White) の手を MO で返す。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    resp_sw = await collect_response(dut)
    # SW 自身は (現状) ER02 応答だが、内部状態は my=White で確定
    assert resp_sw.startswith(b"ER02") or resp_sw == b"\n"

    await send_line(dut, b"MOd3\n")
    resp = await collect_response(dut)
    # 白の応答も "MO<xy>\n" 形式
    assert resp.startswith(b"MO"), f"MO で始まる応答を期待: {resp!r}"
    assert resp.endswith(b"\n")
    assert len(resp) == 5, f"MO<xy>\\n は 5 byte: {resp!r}"

    # 応答の <xy> は実際に white に追加された bit と一致する
    new_white = int(dut.u_game_state.white.value)
    new_bits = new_white & ~INIT_WHITE
    # (反転なしの単純配置なので、追加された bit はちょうど 1 個)
    assert bin(new_bits).count("1") == 1
    added_bit = (new_bits & -new_bits).bit_length() - 1
    expected_xy = bit_to_coord(added_bit).encode()
    assert resp[2:4] == expected_xy, (
        f"応答 xy={resp[2:4]!r} が white の追加 bit {added_bit} ({bit_to_coord(added_bit)}) と不一致"
    )


@cocotb.test()
async def pi_still_returns_po_after_sb(dut) -> None:
    """SB で MO 応答を出した後でも PI は PO を返す (TX モード切替が壊れてない)。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    # 5d-3d で SB 後の応答は MO + BS の 2 行に増えた → 両方消費
    await collect_response(dut)
    await collect_response(dut)
    await send_line(dut, b"PI\n")
    resp = await collect_response(dut)
    assert resp == b"PO\n"


# ===== Step 5d-3d: SB / MO 後に "MO<xy>\n" + "BS<board>\n" を連結送信 =====


def board_to_bs(black_bb: int, white_bb: int) -> bytes:
    """black/white bitboard → BS 用 64 文字 (a1..h8 行優先、0=空 1=黒 2=白)。"""
    out = bytearray()
    for i in range(64):
        if (white_bb >> i) & 1:
            out.append(ord("2"))
        elif (black_bb >> i) & 1:
            out.append(ord("1"))
        else:
            out.append(ord("0"))
    return bytes(out)


@cocotb.test()
async def sb_responds_with_mo_then_bs(dut) -> None:
    """SB → "MOd3\\n" + "BS<board>\\n" の 2 行が連続して返る。

    BS の 64 文字は SB+自分の手反映後の盤面 (反転なし、d3 黒追加) と一致する。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SB\n")
    mo_line = await collect_response(dut)
    bs_line = await collect_response(dut)
    assert mo_line == b"MOd3\n"
    assert bs_line.startswith(b"BS"), f"BS で始まる: {bs_line!r}"
    assert bs_line.endswith(b"\n")
    assert len(bs_line) == 67, f"67 byte: {len(bs_line)}"

    # 盤面 (BS の 64 文字部分) が DUT 内部状態と一致
    dut_board = bs_line[2:-1]
    expected = board_to_bs(int(dut.u_game_state.black.value),
                           int(dut.u_game_state.white.value))
    assert dut_board == expected, (
        f"BS board mismatch:\n  DUT     : {dut_board!r}\n"
        f"  expected: {expected!r}"
    )


@cocotb.test()
async def mo_responds_with_mo_then_bs(dut) -> None:
    """SW → MO<xy> → "MO<my_xy>\\n" + "BS<board>\\n" 2 行。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    await collect_response(dut)   # SW は ER02 のみ (BS は付かない)

    await send_line(dut, b"MOd3\n")
    mo_line = await collect_response(dut)
    bs_line = await collect_response(dut)
    assert mo_line.startswith(b"MO")
    assert bs_line.startswith(b"BS") and len(bs_line) == 67

    # BS の盤面が現在の game_state と一致
    dut_board = bs_line[2:-1]
    expected = board_to_bs(int(dut.u_game_state.black.value),
                           int(dut.u_game_state.white.value))
    assert dut_board == expected


# ===== Step 6: 反転 (flip_calc) 込みで golden apply_move と完全一致 =====


# Path 設定 (golden を import するため)
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
from golden.reversi_rules import (  # noqa: E402
    apply_move as _apply_move,
    fmt_coord as _fmt_coord,
    init_board as _init_board,
    legal_moves as _legal_moves,
    BLACK as _BLACK,
    WHITE as _WHITE,
)


def _board_to_bb(board, target):
    bits = 0
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                bits |= 1 << (r * 8 + c)
    return bits


@cocotb.test()
async def step6_self_play_matches_golden(dut) -> None:
    """SB → 5 手連続 MO で proto の内部盤面が golden と完全一致。

    proto の手選択は pick_lsb (= legal_moves[0])、相手の手も同じく lowest
    を選んで MO で渡す。golden 側で apply_move を流して期待盤面を生成、
    proto.u_game_state.black/white と bit-exact 比較。
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)

    # SB: I'm Black, my first move
    await send_line(dut, b"SB\n")
    await collect_response(dut)
    await collect_response(dut)

    # golden で初手 (黒) を打つ
    board = _init_board()
    my_legal = _legal_moves(board, _BLACK)
    assert my_legal[0] == (2, 3)  # d3
    _apply_move(board, my_legal[0][0], my_legal[0][1], _BLACK)

    # 序盤数手 (PASS が発生しない範囲で) を golden と完全一致確認
    for ply in range(5):
        opp_legal = _legal_moves(board, _WHITE)
        assert opp_legal, f"ply {ply}: 白の合法手が無くなった、test スコープ外"
        opp_move = opp_legal[0]
        opp_coord = _fmt_coord(*opp_move).encode()

        # 送信前に my の合法手有無を予測 (proto が MO+BS を返すか ER02 だけか)
        next_board = [row[:] for row in board]
        _apply_move(next_board, opp_move[0], opp_move[1], _WHITE)
        my_legal_after = _legal_moves(next_board, _BLACK)
        assert my_legal_after, (
            f"ply {ply}: 白の {opp_coord!r} 後に黒の合法手が無い、test スコープ外"
        )

        await send_line(dut, b"MO" + opp_coord + b"\n")
        mo_line = await collect_response(dut)
        bs_line = await collect_response(dut)
        assert mo_line.startswith(b"MO")
        assert bs_line.startswith(b"BS")

        # golden 側でも opp と me を順に適用
        _apply_move(board, opp_move[0], opp_move[1], _WHITE)
        my_move = my_legal_after[0]
        _apply_move(board, my_move[0], my_move[1], _BLACK)

        # 完全一致確認
        expected_black = _board_to_bb(board, _BLACK)
        expected_white = _board_to_bb(board, _WHITE)
        got_black = int(dut.u_game_state.black.value)
        got_white = int(dut.u_game_state.white.value)
        assert got_black == expected_black, (
            f"ply {ply} after opp {opp_coord!r}:\n"
            f"  black got={got_black:#018x} expected={expected_black:#018x}\n"
            f"  diff      ={(got_black ^ expected_black):#018x}"
        )
        assert got_white == expected_white, (
            f"ply {ply}: white got={got_white:#018x} expected={expected_white:#018x}"
        )


@cocotb.test()
async def sw_no_bs_appended(dut) -> None:
    """SW 直後の応答は ER02 のみで BS が続かない (5d-3d の chain は MO に限る)。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset(dut)
    await send_line(dut, b"SW\n")
    line1 = await collect_response(dut)
    assert line1.startswith(b"ER02")

    # 続けて何も来ないことを確認 (PI を投げて PO がそのまま返るか)
    await send_line(dut, b"PI\n")
    line2 = await collect_response(dut)
    assert line2 == b"PO\n", (
        f"SW の後ろに余計な BS があると PO が遅れて見える。実際: {line2!r}"
    )


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
