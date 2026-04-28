# cocotb で rtl/pick_lsb.v を直接 toplevel として検証する。
# 64bit 入力から最下位 set bit を抽出 (純粋組合せ)。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/pick_lsb.v
TOPLEVEL := pick_lsb
MODULE   := test_pick_lsb

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
