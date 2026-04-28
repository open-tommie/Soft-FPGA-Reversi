# Verilator + cocotb で rtl/othello_top.v をユニット検証する。
# 直接 make するのではなく scripts/test-unit.sh から呼ばれる。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/othello_top.v
TOPLEVEL := othello_top
MODULE   := test_othello_top

# Verilator 5.x で必要なオプション
EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
