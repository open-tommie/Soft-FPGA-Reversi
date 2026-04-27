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
# verilated.cpp は Pico 用にパッチした Soft-FPGA-TD4 のものを利用、
# stub_mutex.h で std::mutex / clock_gettime / VlThreadPool / _DEBUG を no-op にする。

set(VERILATOR_BIN /usr/local/bin/verilator)
set(VERILATOR_INC /usr/local/share/verilator/include)
set(RTL_DIR ${CMAKE_SOURCE_DIR}/../rtl)
set(VERILATED_DIR ${CMAKE_BINARY_DIR}/verilated)
set(VERILATOR_RUNTIME ${CMAKE_SOURCE_DIR}/src/verilib/verilated.cpp)

# Verilator は configure 時に実行する。生成 .cpp 名にハッシュが入るため
# (例: ___024root__DepSet_h<hash>__0.cpp)、列挙ではなく GLOB で拾う。
# Verilog を編集した場合は build ディレクトリを消して再 cmake すること。
file(MAKE_DIRECTORY ${VERILATED_DIR})
execute_process(
    COMMAND ${VERILATOR_BIN} --cc --no-trace --no-timing
            --threads 1 --threads-dpi none
            --Mdir ${VERILATED_DIR}
            ${RTL_DIR}/othello_top.v
    RESULT_VARIABLE _verilator_rc
)
if(NOT _verilator_rc EQUAL 0)
    message(FATAL_ERROR "verilator failed (rc=${_verilator_rc})")
endif()
file(GLOB VERILATED_SOURCES CONFIGURE_DEPENDS "${VERILATED_DIR}/*.cpp")

add_executable(firmware
    src/main.cpp
    ${VERILATED_SOURCES}
    ${VERILATOR_RUNTIME}
)

target_include_directories(firmware PRIVATE
    src
    ${VERILATED_DIR}
    ${VERILATOR_INC}
    ${VERILATOR_INC}/vltstd
)

# Verilator 由来のソースには stub_mutex.h を強制 include して
# std::mutex などのスタブを差し込む。
set_source_files_properties(
    ${VERILATED_SOURCES} ${VERILATOR_RUNTIME}
    PROPERTIES COMPILE_FLAGS "-include ${CMAKE_SOURCE_DIR}/src/stub_mutex.h"
)

target_compile_options(firmware PRIVATE
    -Os
    -fno-unwind-tables
    -Wall
    -Wextra
)
target_compile_definitions(firmware PRIVATE NDEBUG)

target_link_libraries(firmware
    pico_stdlib
)

pico_enable_stdio_usb(firmware 1)
pico_enable_stdio_uart(firmware 0)

pico_add_extra_outputs(firmware)
