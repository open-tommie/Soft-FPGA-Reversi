cmake_minimum_required(VERSION 3.13)

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

# Verilator 出力 (Vothello_top) は dynamic_cast を使うので RTTI を有効化。
# pico_sdk_init より前に設定。
set(PICO_CXX_ENABLE_RTTI 1)
set(PICO_CXX_ENABLE_EXCEPTIONS 0)

project(reversi_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# --- Verilator codegen ---
# rtl/othello_top.v を verilator で C++ 化し firmware にリンクする。
# Verilator ランタイム (verilated.cpp) は上流 install を組込み向けに最小パッチ
# したコピーを使う (firmware/src/verilator-runtime/verilated.cpp)。
# パッチ内容はファイル冒頭参照。
# 組込みでホスト前提機能 (mutex / threads / trace) は stub_mutex.h が
# include guard 先取りと最小型 stub で迂回する。

set(VERILATOR_BIN /usr/local/bin/verilator)
set(VERILATOR_INC /usr/local/share/verilator/include)
set(RTL_DIR ${CMAKE_SOURCE_DIR}/../rtl)
set(VERILATED_DIR ${CMAKE_BINARY_DIR}/verilated)
set(VERILATOR_RUNTIME ${CMAKE_SOURCE_DIR}/src/verilator-runtime/verilated.cpp)

# verilator が --threads 無しで生成する .cpp ファイル群。--threads 1 を渡すと
# ファイル名にハッシュ (___024root__DepSet_h<hash>__0.cpp) が入って enumerable
# でなくなるので、threads は省略 (model のデフォルトは threads=1 と同等)。
set(VERILATED_SOURCES
    ${VERILATED_DIR}/Vothello_top.cpp
    ${VERILATED_DIR}/Vothello_top__Syms__Slow.cpp
    ${VERILATED_DIR}/Vothello_top___024root__0.cpp
    ${VERILATED_DIR}/Vothello_top___024root__0__Slow.cpp
    ${VERILATED_DIR}/Vothello_top___024root__Slow.cpp
)

# Verilog ファイルが変わったら自動で再 verilation。
# stamp ファイルを OUTPUT にすることで、verilator 出力複数を 1 つの依存関係に集約。
set(VERILATED_STAMP ${VERILATED_DIR}/.stamp)
file(GLOB RTL_SOURCES CONFIGURE_DEPENDS "${RTL_DIR}/*.v" "${RTL_DIR}/*.sv")

add_custom_command(
    OUTPUT ${VERILATED_STAMP} ${VERILATED_SOURCES}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${VERILATED_DIR}
    COMMAND ${VERILATOR_BIN} --cc --no-trace --no-timing
            -y ${RTL_DIR}
            --Mdir ${VERILATED_DIR}
            ${RTL_DIR}/othello_top.v
    COMMAND ${CMAKE_COMMAND} -E touch ${VERILATED_STAMP}
    DEPENDS ${RTL_SOURCES}
    COMMENT "Verilating othello_top (RTL changed)"
    VERBATIM
)

add_executable(firmware
    src/main.cpp
    src/cxx_minimal.cpp
    ${VERILATED_SOURCES}
    ${VERILATOR_RUNTIME}
)

# 注: LTO (INTERPROCEDURAL_OPTIMIZATION) は Pico SDK の
# `-Wl,--wrap=printf/puts/putchar` と衝突して link エラーになる
# (LTO で printf 呼び出しがインライン化され --wrap が効かない)。
# 採用しない。回避には全 printf 系 TU を -fno-lto にする必要があり
# 得られる効果に対して保守コストが大きい。

target_include_directories(firmware PRIVATE src)
# Verilator 由来のヘッダは 3rd-party 扱い (SYSTEM) にして警告対象から外す。
# これで main.cpp 等が Vothello_top.h 経由で verilated_funcs.h を引いても
# sign-compare 等の警告ノイズが出ない。
target_include_directories(firmware SYSTEM PRIVATE
    ${VERILATED_DIR}
    ${VERILATOR_INC}
    ${VERILATOR_INC}/vltstd
)

# Verilator 由来のソースには:
# - -include stub_mutex.h で std::mutex など組込み向け stub を差し込む
# - -w で 3rd-party 生成コードの警告 (sign-compare 等) を抑止
set_source_files_properties(
    ${VERILATED_SOURCES} ${VERILATOR_RUNTIME}
    PROPERTIES COMPILE_FLAGS "-include ${CMAKE_SOURCE_DIR}/src/stub_mutex.h -w"
)

target_compile_options(firmware PRIVATE
    -Os
    -fno-unwind-tables
    -Wall
    -Wextra
)
target_compile_definitions(firmware PRIVATE
    NDEBUG
    # 当方は %lu / %s / %d しか使わないので float / 指数は要らない。
    # _etoa / _ftoa / _strtod_l / _dtoa_r 等の引きずりを防ぐ (~3-5 KiB)。
    PICO_PRINTF_SUPPORT_FLOAT=0
    PICO_PRINTF_SUPPORT_EXPONENTIAL=0
)

target_link_libraries(firmware
    pico_stdlib
)

pico_enable_stdio_usb(firmware 1)
pico_enable_stdio_uart(firmware 1)

pico_add_extra_outputs(firmware)
