"""Step 1: Hello UF2 の動作を Pico 2 実機で確認する HIL テスト。

main.cpp が `printf("Hello, world!\\n")` を 1 秒周期で出すことを前提とする。
"""
from __future__ import annotations

import time


def test_hello_world_appears(dut, expect):
    """ファームが起動すると "Hello, world!" が一度は出る。"""
    line = expect(dut, r"Hello, world!", timeout=5.0)
    assert "Hello, world!" in line


def test_hello_world_repeats_at_1hz(dut, expect):
    """1 秒周期で繰り返し出力される。

    2 行目までの間隔が 0.5s〜2.0s に収まることだけ確認する
    (Pico SDK の sleep_ms 精度 + USB-CDC バッファのゆらぎを許容)。
    """
    expect(dut, r"Hello, world!", timeout=5.0)
    t0 = time.monotonic()
    expect(dut, r"Hello, world!", timeout=5.0)
    elapsed = time.monotonic() - t0
    assert 0.5 <= elapsed <= 2.0, f"周期がずれている: {elapsed:.2f}s"


def test_no_garbage_on_serial(dut, expect):
    """Hello, world! 以外の不審な行が出ないことの簡易チェック。"""
    expect(dut, r"Hello, world!", timeout=5.0)
    # 続く 3 行を採取
    captured: list[str] = []
    for _ in range(3):
        line = dut.readline().decode("utf-8", errors="replace").rstrip()
        if line:
            captured.append(line)
    assert all("Hello, world!" in l for l in captured), \
        f"想定外の出力: {captured!r}"
