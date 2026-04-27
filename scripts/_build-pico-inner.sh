#!/usr/bin/env bash
set -euo pipefail

# コンテナ内で実行される。直接呼ばず scripts/build-pico.sh から呼び出す。

if [[ ! -f firmware/CMakeLists.txt ]]; then
    echo "firmware/CMakeLists.txt が無い (Hello UF2 のセットアップ未着手)" >&2
    echo "Docker 環境の動作確認のみ:" >&2
    arm-none-eabi-gcc --version
    cmake --version
    ninja --version
    echo "PICO_SDK_PATH=${PICO_SDK_PATH}"
    ls "${PICO_SDK_PATH}/CMakeLists.txt" >/dev/null && echo "Pico SDK OK"
    exit 0
fi

cmake -S firmware -B firmware/build -G Ninja
cmake --build firmware/build
