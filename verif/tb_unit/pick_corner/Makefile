# cocotb で rtl/pick_corner.v を直接 toplevel として検証する。
# 角優先手選択: 角が合法手にあれば角を、なければ pick_lsb にフォールバック。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/pick_lsb.v $(RTL_DIR)/pick_corner.v
TOPLEVEL := pick_corner
MODULE   := test_pick_corner

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
