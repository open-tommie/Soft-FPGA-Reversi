cmake_minimum_required(VERSION 3.13)

# Pico SDK 非依存のホスト版。Docker 内 Ubuntu 24.04 上で
# rtl/othello_top.v を Verilator で C++ 化し、stdin/stdout に接続した
# 単独バイナリ reversi_host を生成する。
#
# 用途: Pico 実機が無くても verif/tb_protocol/scenarios/*.txt 等の
# プロトコル回帰を `./reversi_host < scenario.txt` で食わせられる。
#
# 注意: firmware/CMakeLists.txt とは別ツリー。共有しているのは rtl/ のみ。
# ホスト版は組込みパッチした verilator-runtime/verilated.cpp ではなく
# Verilator 上流の verilated.cpp を使う (RTTI / threads / OS 依存込み)。

project(reversi_host CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Verilator 検出 ---
# Dockerfile は /usr/local 配下にビルド済み。明示的に指す。
set(VERILATOR_BIN /usr/local/bin/verilator)
set(VERILATOR_INC /usr/local/share/verilator/include)
# Verilator 5.x の verilated.cpp は VlThreadPool シンボルを参照するため
# verilated_threads.cpp も同時にリンクする (--threads を渡さなくても必要)。
set(VERILATOR_RUNTIME
    ${VERILATOR_INC}/verilated.cpp
    ${VERILATOR_INC}/verilated_threads.cpp
)

if(NOT EXISTS ${VERILATOR_BIN})
    message(FATAL_ERROR "verilator not found at ${VERILATOR_BIN}")
endif()
foreach(_rt ${VERILATOR_RUNTIME})
    if(NOT EXISTS ${_rt})
        message(FATAL_ERROR "verilator runtime source not found: ${_rt}")
    endif()
endforeach()

set(RTL_DIR ${CMAKE_SOURCE_DIR}/../rtl)
set(VERILATED_DIR ${CMAKE_BINARY_DIR}/verilated)

# firmware 版と enumerable な出力ファイル名を揃えるため --threads は付けない。
set(VERILATED_SOURCES
    ${VERILATED_DIR}/Vothello_top.cpp
    ${VERILATED_DIR}/Vothello_top__Syms__Slow.cpp
    ${VERILATED_DIR}/Vothello_top___024root__0.cpp
    ${VERILATED_DIR}/Vothello_top___024root__0__Slow.cpp
    ${VERILATED_DIR}/Vothello_top___024root__Slow.cpp
)

set(VERILATED_STAMP ${VERILATED_DIR}/.stamp)
file(GLOB RTL_SOURCES CONFIGURE_DEPENDS "${RTL_DIR}/*.v" "${RTL_DIR}/*.sv")

add_custom_command(
    OUTPUT ${VERILATED_STAMP} ${VERILATED_SOURCES}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${VERILATED_DIR}
    COMMAND ${VERILATOR_BIN} --cc --no-trace --no-timing
            -DSIMULATION
            -y ${RTL_DIR}
            --Mdir ${VERILATED_DIR}
            ${RTL_DIR}/othello_top.v
    COMMAND ${CMAKE_COMMAND} -E touch ${VERILATED_STAMP}
    DEPENDS ${RTL_SOURCES}
    COMMENT "Verilating othello_top (host build)"
    VERBATIM
)

add_executable(reversi_host
    main.cpp
    ${VERILATED_SOURCES}
    ${VERILATOR_RUNTIME}
)

# Verilator 由来のヘッダは 3rd-party 扱いで警告対象外。
target_include_directories(reversi_host SYSTEM PRIVATE
    ${VERILATED_DIR}
    ${VERILATOR_INC}
    ${VERILATOR_INC}/vltstd
)

# Verilator 生成コードと上流 runtime は -w で警告抑止 (sign-compare 等のノイズ)。
set_source_files_properties(
    ${VERILATED_SOURCES} ${VERILATOR_RUNTIME}
    PROPERTIES COMPILE_FLAGS "-w"
)

target_compile_options(reversi_host PRIVATE
    -O2
    -Wall
    -Wextra
)

# Verilator 上流 runtime は pthread を要求する (--threads 無しでも mutex 参照あり)。
find_package(Threads REQUIRED)
target_link_libraries(reversi_host PRIVATE Threads::Threads)
