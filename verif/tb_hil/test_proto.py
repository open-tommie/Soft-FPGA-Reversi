"""UART テキストプロトコル (PI/VE/ER02/SB/PA) の HIL テスト。

実機 firmware (rtl/proto.v) の応答を /dev/ttyACM* 経由で確認する。
詳細仕様は etc/protocol.md を参照。
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture(autouse=True)
def reset_to_idle(dut) -> None:
    """各テスト前に EB を送って firmware を IDLE 状態に戻す。

    EB は無応答コマンドなので、送信後に短く待ってから入力バッファを掃除する。
    SB を打ったテストの後でも次のテストが空の盤面から始まる。
    """
    dut.reset_input_buffer()
    dut.write(b"EB\r\n")
    time.sleep(0.05)
    dut.reset_input_buffer()


def test_pi_returns_po(dut, expect) -> None:
    """PI を投げると PO が返る (Ping)。"""
    dut.write(b"PI\r\n")
    line = expect(dut, r"^PO$", timeout=2.0)
    assert line == "PO"


def test_ve_returns_version(dut, expect) -> None:
    """VE を投げると VE01<name> が返る (Version)。"""
    dut.write(b"VE\r\n")
    line = expect(dut, r"^VE01", timeout=2.0)
    # 名前部は実装依存だが、空ではない 1 文字以上が続くこと
    assert len(line) > len("VE01"), f"VE 応答に名前が無い: {line!r}"


@pytest.mark.parametrize("cmd", [b"MO\r\n", b"BO\r\n", b"SW\r\n"])
def test_known_but_unimplemented_returns_er02(dut, expect, cmd: bytes) -> None:
    """既知コマンドだが現状未実装のもの (MO 単体 / BO / SW) は ER02 で返る。

    SB / PA は実装済みのため、別テストで MO+BS 応答を検証する。
    """
    dut.write(cmd)
    line = expect(dut, r"^ER02", timeout=2.0)
    assert line.startswith("ER02"), f"ER02 を期待: {line!r}"


def test_unknown_command_returns_er02(dut, expect) -> None:
    """未知の 2 文字コマンドは ER02 で拒否される。"""
    dut.write(b"XX\r\n")
    line = expect(dut, r"^ER02", timeout=2.0)
    assert "unknown" in line.lower(), f"ER02 unknown を期待: {line!r}"


def test_lowercase_command_returns_er02(dut, expect) -> None:
    """小文字コマンドは ER02 (大文字 2 文字必須)。"""
    dut.write(b"pi\r\n")
    line = expect(dut, r"^ER02", timeout=2.0)
    assert line.startswith("ER02")


def test_pi_can_be_sent_repeatedly(dut, expect) -> None:
    """PI を連続で投げて PO が同数返る (パーサが行を取りこぼさない)。"""
    dut.write(b"PI\r\n" * 5)
    for _ in range(5):
        expect(dut, r"^PO$", timeout=2.0)


def test_sb_returns_mo_then_bs(dut, expect) -> None:
    """SB を投げると黒の初手 MOd3 と BS<board> が返る (Step 6 で実装済み)。

    pick_lsb は行優先 LSB なので決定的に d3 (黒の最下位合法手) を選ぶ。
    """
    dut.write(b"SB\r\n")
    mo = expect(dut, r"^MO[a-h][1-8]$", timeout=2.0)
    assert mo == "MOd3", f"黒の初手は決定的に MOd3: {mo!r}"
    bs = expect(dut, r"^BS", timeout=2.0)
    assert len(bs) == 66, f"BS<64char> = 66 char: {bs!r}"


def test_pa_after_sb_returns_my_move(dut, expect) -> None:
    """SB → PA (相手パス) で自分の次の手が MO+BS で返る (Step 7 で実装済み)。"""
    dut.write(b"SB\r\n")
    expect(dut, r"^MO", timeout=2.0)   # 自分の初手 MOd3
    expect(dut, r"^BS", timeout=2.0)   # BS<board>

    dut.write(b"PA\r\n")
    mo = expect(dut, r"^MO[a-h][1-8]$", timeout=2.0)
    assert mo.startswith("MO")
    bs = expect(dut, r"^BS", timeout=2.0)
    assert len(bs) == 66
