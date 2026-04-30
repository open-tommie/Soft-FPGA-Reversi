"""Bootstrap step 3: UART テキストプロトコル骨格 (PI/VE) の HIL テスト。

firmware/src/proto.cpp の最小実装が想定通りに応答するかを実機で確認する。
詳細仕様は etc/protocol.md を参照。
"""
from __future__ import annotations

import pytest


def test_pi_returns_po(dut, expect) -> None:
    """PI を投げると PO が返る (Ping)。"""
    dut.reset_input_buffer()
    dut.write(b"PI\r\n")
    line = expect(dut, r"^PO$", timeout=2.0)
    assert line == "PO"


def test_ve_returns_version(dut, expect) -> None:
    """VE を投げると VE01<name> が返る (Version)。"""
    dut.reset_input_buffer()
    dut.write(b"VE\r\n")
    line = expect(dut, r"^VE01", timeout=2.0)
    # 名前部は実装依存だが、空ではない 1 文字以上が続くこと
    assert len(line) > len("VE01"), f"VE 応答に名前が無い: {line!r}"


@pytest.mark.parametrize("cmd", [b"MO\r\n", b"PA\r\n", b"BO\r\n", b"SB\r\n", b"SW\r\n"])
def test_known_but_unimplemented_returns_er02(dut, expect, cmd: bytes) -> None:
    """既知コマンドだが骨格段階で未実装のものは ER02 で返る。"""
    dut.reset_input_buffer()
    dut.write(cmd)
    line = expect(dut, r"^ER02", timeout=2.0)
    assert line.startswith("ER02"), f"ER02 を期待: {line!r}"


def test_unknown_command_returns_er02(dut, expect) -> None:
    """未知の 2 文字コマンドは ER02 で拒否される。"""
    dut.reset_input_buffer()
    dut.write(b"XX\r\n")
    line = expect(dut, r"^ER02", timeout=2.0)
    assert "unknown" in line.lower(), f"ER02 unknown を期待: {line!r}"


def test_lowercase_command_returns_er02(dut, expect) -> None:
    """小文字コマンドは ER02 (大文字 2 文字必須)。"""
    dut.reset_input_buffer()
    dut.write(b"pi\r\n")
    line = expect(dut, r"^ER02", timeout=2.0)
    assert line.startswith("ER02")


def test_pi_can_be_sent_repeatedly(dut, expect) -> None:
    """PI を連続で投げて PO が同数返る (パーサが行を取りこぼさない)。"""
    dut.reset_input_buffer()
    dut.write(b"PI\r\n" * 5)
    for _ in range(5):
        expect(dut, r"^PO$", timeout=2.0)
