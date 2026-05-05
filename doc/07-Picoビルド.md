# 07-Picoビルド (Pico 2 ターゲット)

Pico SDK + arm-none-eabi-gcc で `firmware/build/firmware.uf2` を生成し、
Raspberry Pi Pico 2 (RP2350) に書き込む手順。

ホスト上で動かす場合は [06-ホストビルド](06-ホストビルド.md) を参照。

## ツールチェイン

[`docker/Dockerfile`](../docker/Dockerfile) でピン留め。**変更時は組合せ全体を再検証**すること。

| ツール | バージョン | 備考 |
| --- | --- | --- |
| Pico SDK | 2.2.0 | RP2350 / pico2 ボード |
| arm-none-eabi-gcc | xPack 15.2.1-1.1 | apt の 13.2 系では Verilator runtime が必要な PRI 系 / TLS 関連で NG |
| Verilator | 5.048 | 上流 `verilated.cpp` を組込み向けに 4 箇所だけパッチして同梱 |
| openocd | RasPi fork (rpi-common, SHA `acff23ff`) | RP2350 cfg 同梱 |
| `verilated.cpp` | 上流 5.048 + 自前最小パッチ | `firmware/src/verilator-runtime/verilated.cpp`、ファイル冒頭にパッチ意図記載 |

## ビルド手順

### Docker イメージのビルド（初回のみ、約 10 分）

```bash
USER_UID=$(id -u) USER_GID=$(id -g) \
    docker compose -f docker/compose.yml build dev
```

### ファームウェアビルド

```bash
./scripts/build-pico.sh
# → firmware/build/firmware.uf2 が生成される
```

クリーンビルドが必要な場合:

```bash
rm -rf firmware/build && ./scripts/build-pico.sh
```

## 書き込み

### BOOTSEL で書き込む（Probe 不要）

1. Pico 2 の BOOTSEL ボタンを押しながら USB 接続
2. Windows のエクスプローラに `RPI-RP2350` ドライブが現れる
3. `firmware/build/firmware.uf2` をドラッグ＆ドロップ
4. 自動リセット後、オンボード LED が 2 Hz で点滅

### Debug Probe で書き込む（SWD）

事前に Probe を WSL2 に attach 済みであること（→ [02-準備](02-準備.md) の usbipd 手順）。

```bash
./scripts/flash.sh
# → Programming → Verified OK → shutdown
```

## シリアルモニタ

WSL2 側:

```bash
sudo apt-get install -y picocom
picocom -b 115200 /dev/ttyACM0
# 終了は Ctrl-A → Ctrl-X
```

Windows 側で見るなら `usbipd detach --busid <Pico>` してから VSCode の
Serial Monitor で COM ポートを開く。

## XI コマンド（デバイス情報）

`XI\r\n` を送るとデバイス情報を返す（RUP v0.2 拡張コマンド）。

```text
送信: XI
応答: +XI pf=rp2350-arm-s flash=4096KB prog=128KB(3%) ram=520KB bss=48KB(9%) clk=150MHz chip=B2 git=abc1234 bld=2026-04-29
```

| フィールド | 内容 | 取得元 |
| --- | --- | --- |
| `pf=` | プラットフォーム | `PICO_PLATFORM` |
| `flash=` | フラッシュ総量 (KB) | `PICO_FLASH_SIZE_BYTES`（コンパイル時定数） |
| `prog=` | フラッシュ使用量 KB と % | リンカシンボル `__flash_binary_end - __flash_binary_start` |
| `ram=` | SRAM 総量 (KB) | RP2350 固定値 520 KB |
| `bss=` | 静的 SRAM 使用量 KB と % | リンカシンボル `__bss_end__ - SRAM_BASE(0x20000000)` |
| `clk=` | システムクロック (MHz) | `clock_get_hz(clk_sys)` |
| `chip=` | チップリビジョン | `SYSINFO CHIP_ID[31:28]`（0=B0, 1=B1, 2=B2） |
| `git=` | git ショートハッシュ（`+` = ダーティ） | CMake で `git rev-parse --short HEAD` |
| `bld=` | ビルド日（ISO 形式） | `__DATE__` マクロを YYYY-MM-DD に変換 |

`bss=` は data + bss セクションの末尾アドレス。ヒープ・スタックは含まない。

## バイナリサイズ実績

| 構成 | text | bss | UF2 |
| --- | ---: | ---: | ---: |
| Hello UF2 (Step 1) | 28,296 B | 3,784 B | 49 KB |
| Step 5 完了 (MO/BS) | 64,876 B | 4,836 B | ~190 KB |
| Step 6 完了 (反転入り) | 69,132 B | 4,836 B | ~200 KB |

RP2350 の 2 MB flash の 3.5%、520 KB SRAM の 1% を消費。

### サイズ最適化の注意点

- `__cxa_demangle` 経路は stub 化済（Step 中盤で 34 KiB 削減済）
- **LTO は Pico SDK の `--wrap=printf` と衝突するため不採用**
- 将来サイズが問題になったら `scripts/size.sh --bloaty-diff` で計測

## トラブルシューティング

| 症状 | 原因 / 対処 |
| --- | --- |
| `unable to find a matching CMSIS-DAP device` | Probe を attach し忘れ。`usbipd list` で State を確認 |
| `/dev/ttyACM0` が現れない | usbipd attach が外れた、または Pico がまだ BOOTSEL のまま |
| `Permission denied` on `/dev/ttyACM0` | `dialout` グループ未参加。`usermod` 後に再ログイン |
| `usbipd attach` が "device is busy" | Windows 側で既に COM ポートを開いている。Serial Monitor を閉じる |
| Docker ビルドが jimtcl で失敗 | `--enable-internal-jimtcl` 抜けの可能性。`docker/Dockerfile` を確認 |
| firmware build が `PRIu64` / `__aeabi_read_tp` 未定義で落ちる | arm-gcc が apt の 13.2 になっている。xPack への切替を確認 (`docker/Dockerfile` の `XPACK_ARM_GCC_VER`) |
| 起動直後に `VerilatedContext thread count mismatch with model` で abort | bare-metal で `hardware_concurrency()=0` になるための既知挙動。`firmware/src/verilator-runtime/verilated.cpp` の thread check が no-op になっているか確認 |

## 関連

- [02-準備](02-準備.md) — usbipd-win セットアップ、WSL2 デバイス確認
- [04-Docker 構成](04-Docker構成.md) — Docker イメージ詳細
- [05-進捗メモ](05-進捗メモ.md) — ブートストラップ進捗・Step 別サイズ推移
- [06-ホストビルド](06-ホストビルド.md) — Pico 不要モード（ホスト ELF）
- [`../firmware/CMakeLists.txt`](../firmware/CMakeLists.txt) — ビルド定義
- [`../scripts/build-pico.sh`](../scripts/build-pico.sh) — ビルドスクリプト
- [`../scripts/flash.sh`](../scripts/flash.sh) — 書き込みスクリプト
