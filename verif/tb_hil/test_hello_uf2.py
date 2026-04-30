"""ファームウェア基本疎通の HIL smoke test。

旧 Step 1 の `Hello, world!` 出力テストは proto.v 統合 (Step 3+) で
main.cpp から該当 printf が削除されたため、現在のファームウェアでは
意味を成さない。代わりに以下の最小疎通を検証する:

    - PI を投げると PO が返る (UART テキストプロトコル疎通)
    - VE で VE01 prefix の応答が返る (バージョン応答)
    - 起動直後の不審な余分バイトが無い (静かに待機している)

これにより「ファームウェアが起動して、UART を喋れる」基本要件を担保する。
"""
from __future__ import annotations

import time


def test_pi_smoke(dut, expect):
    """ファームが起動していて PI に PO で応答する。"""
    dut.reset_input_buffer()
    dut.write(b"PI\r\n")
    line = expect(dut, r"^PO$", timeout=5.0)
    assert line == "PO"


def test_ve_smoke(dut, expect):
    """VE が VE01 prefix で応答する。"""
    dut.reset_input_buffer()
    dut.write(b"VE\r\n")
    line = expect(dut, r"^VE01", timeout=5.0)
    assert line.startswith("VE01"), f"VE01 prefix を期待: {line!r}"


def test_idle_serial_is_quiet(dut):
    """無入力時に不審な余分バイトが出てこない (起動後 0.5s 採取して空)。"""
    dut.reset_input_buffer()
    time.sleep(0.5)
    leftover = dut.read(dut.in_waiting or 0)
    assert not leftover, f"アイドル時に余分なバイト: {leftover!r}"
