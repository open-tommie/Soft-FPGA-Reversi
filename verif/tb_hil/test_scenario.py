"""シナリオ回帰テスト: verif/golden/scenarios/*.txt を実機 firmware に流す。

シナリオファイル形式 (`scenarios/*.txt`):
    TX <cmd>  … ホスト側が firmware に送るコマンド (改行なし)
    RX <resp> … firmware から期待される応答
    #         … コメント行、空行は無視

firmware は MO の後に BS<board> を追加送信するが、シナリオには含まれないため
受信側で読み飛ばす。PI/PO も同様に除外する。

VE 応答は実装名が異なるため prefix "VE01" のみ照合する。
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "verif" / "golden" / "scenarios"
_SCENARIO_FILES = sorted(SCENARIOS_DIR.glob("*.txt"))

# firmware が応答として追加送信する行のうち、シナリオ照合から除外するプレフィックス
_SKIP_PREFIXES = frozenset({"BS", "PI", "PO"})


def _parse(path: Path) -> list[tuple[str, str]]:
    """(kind, text) のリストを返す。kind は "TX" または "RX"。"""
    steps: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("TX "):
            steps.append(("TX", s[3:]))
        elif s.startswith("RX "):
            steps.append(("RX", s[3:]))
    return steps


def _recv(dut, timeout: float = 5.0) -> str:
    """BS / PI / PO を読み飛ばして次の有効行を返す。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = dut.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").rstrip()
        if line[:2] in _SKIP_PREFIXES:
            continue
        return line
    raise AssertionError(f"応答タイムアウト ({timeout:.1f}s)")


def _match(actual: str, expected: str) -> bool:
    """VE 応答は "VE01" prefix 一致、それ以外は完全一致。"""
    if expected.startswith("VE01"):
        return actual.startswith("VE01")
    return actual == expected


@pytest.fixture(autouse=True)
def reset_firmware(dut) -> None:
    """各テスト前に EB を送って firmware を IDLE 状態に戻す。
    EB は無応答なので送信後に入力バッファをクリアするだけでよい。
    """
    dut.reset_input_buffer()
    dut.write(b"EB\r\n")
    time.sleep(0.05)
    dut.reset_input_buffer()


@pytest.mark.parametrize(
    "scenario_path",
    _SCENARIO_FILES,
    ids=[p.name for p in _SCENARIO_FILES],
)
def test_scenario(dut, scenario_path: Path) -> None:
    """TX/RX シナリオを firmware に流して応答を照合する。"""
    steps = _parse(scenario_path)
    for step_i, (kind, text) in enumerate(steps):
        if kind == "TX":
            dut.write(f"{text}\r\n".encode("ascii"))
        else:
            actual = _recv(dut)
            assert _match(actual, text), (
                f"step {step_i}: expected={text!r}  actual={actual!r}\n"
                f"  ({scenario_path.name})"
            )
