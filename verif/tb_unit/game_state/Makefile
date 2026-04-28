# cocotb で rtl/game_state.v を直接 toplevel として検証する。
# 内部盤面 + side + phase を保持する純粋なレジスタファイル。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/game_state.v
TOPLEVEL := game_state
MODULE   := test_game_state

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
