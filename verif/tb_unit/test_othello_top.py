"""rtl/othello_top.v の cocotb ユニットテスト。

現状のスタブ DUT は `tick` カウンタ 1 個のみ:
- rst==1 で tick = 0
- rst==0 で posedge clk ごとに tick += 1

この最小契約だけを cocotb で検証する。手順 4 (legal_bb 実装) で
契約が増えたらここに追加していく。
"""
from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLK_PERIOD_NS = 10


async def _reset(dut):
    """rst を 2 サイクル叩いて 0 に解放。
    cocotb-Verilator では `value =` の書込みが次 delta cycle で反映される
    ため、書込み後に 1 サイクル余分に進めて確実に rst=0 を取り込ませる。
    """
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)  # この edge で rst=0 が反映される (tick はまだ 0)


@cocotb.test()
async def reset_holds_tick_at_zero(dut):
    """rst==1 を維持している間 tick==0。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    dut.rst.value = 1
    for _ in range(3):
        await RisingEdge(dut.clk)
        assert int(dut.tick.value) == 0


@cocotb.test()
async def tick_increments_each_clock(dut):
    """rst 解放後、tick が 1 サイクルずつ単調増加する。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)
    prev = int(dut.tick.value)
    for i in range(16):
        await RisingEdge(dut.clk)
        cur = int(dut.tick.value)
        assert cur == prev + 1, f"step {i}: tick {prev} -> {cur} (期待 +1)"
        prev = cur


@cocotb.test()
async def reset_re_zeroes_after_running(dut):
    """走らせた後でも rst==1 を 1 サイクル叩けば 0 に戻る。"""
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await _reset(dut)
    for _ in range(5):
        await RisingEdge(dut.clk)
    assert int(dut.tick.value) > 0  # 走っていることの確認

    dut.rst.value = 1
    await RisingEdge(dut.clk)  # この edge で rst=1 が取り込まれる (まだ加算)
    await RisingEdge(dut.clk)  # この edge で 0 になる
    assert int(dut.tick.value) == 0
