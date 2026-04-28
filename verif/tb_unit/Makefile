# Verilator + cocotb で rtl/proto.v を直接ユニット検証する。
# 直接 make するのではなく scripts/test-unit.sh から呼ばれる。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/proto.v
TOPLEVEL := proto
MODULE   := test_proto

# Verilator 5.x で必要なオプション
EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
