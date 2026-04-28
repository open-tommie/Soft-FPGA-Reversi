# cocotb で rtl/coord.v を直接 toplevel として検証する。
# 座標 ('a1'..'h8') ↔ bit_index (0..63) の双方向変換と invalid 入力。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/coord.v
TOPLEVEL := coord
MODULE   := test_coord

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
