"""HIL テスト用 pytest フィクスチャ。

セッション単位で Debug Probe 経由のフラッシュ書き込みを 1 回だけ実行し、
各テストには `dut` (USB-CDC `serial.Serial`) と `expect` (行マッチヘルパ) を提供する。

CLI オプション:
    --elf PATH      書き込む ELF (既定: firmware/build/firmware.elf)
    --port PORT     USB-CDC ポート (既定: /dev/ttyACM0)
    --baud BAUD     ボーレート (既定: 115200)
    --no-flash      フラッシュをスキップして実行中ファームに対してテストする

使い方:
    pytest verif/tb_hil
    pytest verif/tb_hil --no-flash --port /dev/ttyACM1
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest
import serial

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ELF = REPO_ROOT / "firmware" / "build" / "firmware.elf"
DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUD = 115200


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--elf", default=str(DEFAULT_ELF),
                     help="書き込む ELF (既定: firmware/build/firmware.elf)")
    parser.addoption("--port", default=DEFAULT_PORT,
                     help="USB-CDC ポート (既定: /dev/ttyACM0)")
    parser.addoption("--baud", type=int, default=DEFAULT_BAUD,
                     help="ボーレート (既定: 115200)")
    parser.addoption("--no-flash", action="store_true",
                     help="既に書き込み済みのファームに対してテストする")


@pytest.fixture(scope="session")
def elf_path(pytestconfig: pytest.Config) -> Path:
    p = Path(pytestconfig.getoption("--elf"))
    if not p.exists():
        pytest.skip(f"ELF が見つからない: {p}\n  scripts/build-pico.sh を先に実行")
    return p


@pytest.fixture(scope="session")
def flashed_firmware(pytestconfig: pytest.Config, elf_path: Path) -> Path:
    """セッション開始時に 1 回だけ Debug Probe 経由でフラッシュ。

    実行環境を判定して docker-in-docker を回避する:
        SFR_IN_CONTAINER=1 (test-hil コンテナ内): _flash-inner.sh を直接呼ぶ
        それ以外 (WSL2 ホスト直 pytest)         : flash.sh を呼ぶ (内部で docker run)
    """
    if pytestconfig.getoption("--no-flash"):
        return elf_path

    if os.environ.get("SFR_IN_CONTAINER") == "1":
        flash = REPO_ROOT / "scripts" / "_flash-inner.sh"
    else:
        flash = REPO_ROOT / "scripts" / "flash.sh"
    subprocess.check_call([str(flash), str(elf_path)])
    # Pico がリセット後に CDC を再列挙するまで待つ。
    # 永続バインド + auto-attach 設定下では不要だが、保険で入れる。
    time.sleep(1.5)
    return elf_path


@pytest.fixture
def dut(pytestconfig: pytest.Config, flashed_firmware: Path):
    port = pytestconfig.getoption("--port")
    baud = pytestconfig.getoption("--baud")
    # CDC が現れるまで最大 3 秒リトライ
    last_err: Exception | None = None
    for _ in range(30):
        try:
            s = serial.Serial(port, baud, timeout=2.0)
            break
        except (serial.SerialException, OSError) as e:
            last_err = e
            time.sleep(0.1)
    else:
        raise RuntimeError(
            f"USB-CDC を開けない: {port}\n"
            f"  scripts/wsl-attach.sh で attach 済みか確認してください\n"
            f"  最後のエラー: {last_err}"
        )
    s.reset_input_buffer()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def expect():
    """`expect(dut, pattern, timeout=5.0)` で正規表現マッチ行を待つ。

    マッチした最初の行 (rstrip 済みデコード文字列) を返す。
    タイムアウト時は AssertionError。
    """
    def _expect(dut: serial.Serial, pattern: str, timeout: float = 5.0) -> str:
        rx = re.compile(pattern)
        deadline = time.monotonic() + timeout
        seen: list[str] = []
        while time.monotonic() < deadline:
            raw = dut.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip()
            seen.append(line)
            if rx.search(line):
                return line
        raise AssertionError(
            f"パターン {pattern!r} が {timeout}s 以内に出現しなかった\n"
            f"  受信した行: {seen[-10:]!r}"
        )
    return _expect
