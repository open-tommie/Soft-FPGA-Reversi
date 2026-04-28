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
