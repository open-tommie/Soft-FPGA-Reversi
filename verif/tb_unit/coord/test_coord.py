"""rtl/coord.v の cocotb 検証。

純粋組合せ論理なので clock 不要。Timer(1, ns) で settle するだけ。

検証カテゴリ:
  A. parse_all_64       'a1'..'h8' の全 64 マスを bit 0..63 にマップ
  B. format_all_64      bit 0..63 を 'a1'..'h8' に展開
  C. round_trip         parse(format(b)) == b、format(parse(c)) == c
  D. invalid_inputs     大文字 / 範囲外文字 / 数字外で parse_valid=0
"""
from __future__ import annotations

import cocotb
from cocotb.triggers import Timer


def coord_to_bit(coord: str) -> int:
    """'d3' → bit_index (= 19)。golden 規約: bit = row*8 + col, a1=0。"""
    col = ord(coord[0]) - ord("a")
    row = ord(coord[1]) - ord("1")
    return row * 8 + col


def bit_to_coord(bit: int) -> str:
    """bit_index → 'd3' のような小文字 2 文字座標。"""
    col = bit & 0x7
    row = (bit >> 3) & 0x7
    return f"{chr(ord('a') + col)}{chr(ord('1') + row)}"


async def settle(dut) -> None:
    """純粋組合せ DUT を settle させる。"""
    await Timer(1, unit="ns")


async def do_parse(dut, col_char: str, row_char: str) -> tuple[int, int]:
    dut.in_col_char.value = ord(col_char)
    dut.in_row_char.value = ord(row_char)
    await settle(dut)
    return int(dut.parse_bit.value), int(dut.parse_valid.value)


async def do_format(dut, bit_index: int) -> tuple[int, int]:
    dut.in_bit_index.value = bit_index
    await settle(dut)
    return int(dut.out_col_char.value), int(dut.out_row_char.value)


# ============================================================
# A. parse: 全 64 マス
# ============================================================
@cocotb.test()
async def parse_all_64(dut) -> None:
    for bit in range(64):
        coord = bit_to_coord(bit)
        got_bit, got_valid = await do_parse(dut, coord[0], coord[1])
        assert got_valid == 1, f"{coord} should be valid"
        assert got_bit == bit, (
            f"{coord}: expected bit {bit} ({bit:#x}), got {got_bit} ({got_bit:#x})"
        )


# ============================================================
# B. format: 全 64 bit
# ============================================================
@cocotb.test()
async def format_all_64(dut) -> None:
    for bit in range(64):
        col_char, row_char = await do_format(dut, bit)
        expected = bit_to_coord(bit)
        got = chr(col_char) + chr(row_char)
        assert got == expected, (
            f"bit {bit}: expected {expected!r}, got {got!r}"
        )


# ============================================================
# C. round-trip
# ============================================================
@cocotb.test()
async def round_trip(dut) -> None:
    """format(b) してその出力を parse すると b に戻る。"""
    for bit in range(64):
        col_char, row_char = await do_format(dut, bit)
        got_bit, got_valid = await do_parse(dut, chr(col_char), chr(row_char))
        assert got_valid == 1
        assert got_bit == bit, f"round-trip bit={bit}: got {got_bit}"


# ============================================================
# D. invalid inputs
# ============================================================
@cocotb.test()
async def invalid_inputs(dut) -> None:
    """大文字 / 範囲外で parse_valid=0。"""
    cases = [
        # 大文字 (etc/protocol.md §4: 小文字必須)
        ("A", "1"), ("a", "0"), ("a", "9"),
        # 範囲外
        ("`", "1"),  # 'a' の 1 つ前
        ("i", "1"),  # 'h' の 1 つ後
        ("a", "0"),  # '1' の 1 つ前
        ("a", ":"),  # '8' の 1 つ後
        # 完全に範囲外の文字
        ("z", "9"),
        ("1", "a"),
        (" ", " "),
        ("\x00", "\x00"),
    ]
    for col_char, row_char in cases:
        _, got_valid = await do_parse(dut, col_char, row_char)
        assert got_valid == 0, (
            f"({col_char!r}, {row_char!r}) should be invalid, got valid=1"
        )

    # 一方だけ valid な組合せも invalid
    _, got_valid = await do_parse(dut, "a", "0")
    assert got_valid == 0, "valid col + invalid row should be invalid"
    _, got_valid = await do_parse(dut, "i", "1")
    assert got_valid == 0, "invalid col + valid row should be invalid"


# ============================================================
# E. 代表点の手動確認 (ドキュメント的)
# ============================================================
@cocotb.test()
async def specific_coords(dut) -> None:
    """良く出てくる座標を念のため手動チェック。"""
    samples = [
        ("a1", 0),
        ("h1", 7),
        ("a8", 56),
        ("h8", 63),
        ("d4", 27),  # 初期局面の白駒
        ("e4", 28),  # 初期局面の黒駒
        ("d5", 35),  # 初期局面の黒駒
        ("e5", 36),  # 初期局面の白駒
        ("d3", 19),  # 黒の初期合法手の 1 つ
    ]
    for coord, expected_bit in samples:
        got_bit, got_valid = await do_parse(dut, coord[0], coord[1])
        assert got_valid == 1, f"{coord} should be valid"
        assert got_bit == expected_bit, (
            f"{coord}: expected bit {expected_bit}, got {got_bit}"
        )
