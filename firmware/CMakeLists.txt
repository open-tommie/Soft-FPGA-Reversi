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
set(VERILATOR_RUNTIME ${CMAKE_SOURCE_DIR}/src/verilator-runtime/verilated.cpp)

file(GLOB RTL_SOURCES CONFIGURE_DEPENDS "${RTL_DIR}/*.v" "${RTL_DIR}/*.sv")

# --- ビルドメタデータ ---
execute_process(
    COMMAND git rev-parse --short HEAD
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    OUTPUT_VARIABLE GIT_HASH
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET)
execute_process(
    COMMAND git diff-index --quiet HEAD
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    RESULT_VARIABLE GIT_IS_DIRTY
    ERROR_QUIET)
if(GIT_IS_DIRTY)
    string(APPEND GIT_HASH "+")
endif()
if(NOT GIT_HASH)
    set(GIT_HASH "unknown")
endif()

# --- ファームウェアターゲット生成関数 ---
# 引数:
#   TARGET_NAME       実行ファイル名 (firmware_lsb / firmware_max_gain)
#   PICK_STRATEGY_VAL Verilog パラメータ値 (0=LSB, 1=MAX_GAIN)
#
# 注: LTO は Pico SDK の --wrap=printf/puts/putchar と衝突して link エラーになる
# (LTO で printf がインライン化され --wrap が効かない) ため採用しない。
function(add_reversi_firmware TARGET_NAME PICK_STRATEGY_VAL)
    set(VERILATED_DIR ${CMAKE_BINARY_DIR}/verilated_${TARGET_NAME})

    # configure 時に Verilator を実行。RTL ファイルが変わると CONFIGURE_DEPENDS で
    # cmake が自動再実行されるため、ビルド時の custom_command と同等の再 verilation が得られる。
    # pick_max_gain は 64 flip_calc インスタンスで出力ファイル数が可変になるため
    # file(GLOB) で列挙する方式を採用。
    execute_process(
        COMMAND ${CMAKE_COMMAND} -E make_directory ${VERILATED_DIR}
    )
    execute_process(
        COMMAND ${VERILATOR_BIN} --cc --no-trace --no-timing
                -y ${RTL_DIR}
                --Mdir ${VERILATED_DIR}
                -GPICK_STRATEGY=${PICK_STRATEGY_VAL}
                ${RTL_DIR}/othello_top.v
        RESULT_VARIABLE _vl_result
    )
    if(NOT _vl_result EQUAL 0)
        message(FATAL_ERROR "Verilator failed for ${TARGET_NAME} (PICK_STRATEGY=${PICK_STRATEGY_VAL})")
    endif()

    file(GLOB VERILATED_SOURCES CONFIGURE_DEPENDS "${VERILATED_DIR}/Vothello_top*.cpp")

    add_executable(${TARGET_NAME}
        src/main.cpp
        src/cxx_minimal.cpp
        ${VERILATED_SOURCES}
        ${VERILATOR_RUNTIME}
    )

    target_include_directories(${TARGET_NAME} PRIVATE src)
    # Verilator 由来のヘッダは 3rd-party 扱い (SYSTEM) にして警告対象から外す。
    target_include_directories(${TARGET_NAME} SYSTEM PRIVATE
        ${VERILATED_DIR}
        ${VERILATOR_INC}
        ${VERILATOR_INC}/vltstd
    )

    # Verilator 由来のソース: stub_mutex.h を差し込み、警告を抑止。
    set_source_files_properties(
        ${VERILATED_SOURCES} ${VERILATOR_RUNTIME}
        PROPERTIES COMPILE_FLAGS "-include ${CMAKE_SOURCE_DIR}/src/stub_mutex.h -w"
    )

    target_compile_options(${TARGET_NAME} PRIVATE
        -Os
        -fno-unwind-tables
        -Wall
        -Wextra
    )

    target_compile_definitions(${TARGET_NAME} PRIVATE
        NDEBUG
        PICO_PRINTF_SUPPORT_FLOAT=0
        PICO_PRINTF_SUPPORT_EXPONENTIAL=0
        GIT_HASH="${GIT_HASH}"
        PICO_PLATFORM_STR="${PICO_PLATFORM}"
    )

    target_link_libraries(${TARGET_NAME}
        pico_stdlib
        hardware_clocks
    )

    pico_enable_stdio_usb(${TARGET_NAME} 1)
    pico_enable_stdio_uart(${TARGET_NAME} 1)
    pico_add_extra_outputs(${TARGET_NAME})
endfunction()

# --- ターゲット定義 ---
add_reversi_firmware(firmware_lsb      0)  # 行優先最初の合法手
add_reversi_firmware(firmware_max_gain 1)  # 反転駒数最大の合法手
add_reversi_firmware(firmware_corner   2)  # 角優先
