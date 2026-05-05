# cocotb で rtl/pick_max_gain.v を直接 toplevel として検証する。
# flip_calc を内部でインスタンス化するため両方を VERILOG_SOURCES に含める。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/flip_calc.v $(RTL_DIR)/pick_max_gain.v
TOPLEVEL := pick_max_gain
MODULE   := test_pick_max_gain

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
