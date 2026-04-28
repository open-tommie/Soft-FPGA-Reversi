# cocotb で rtl/flip_calc.v を直接 toplevel として検証する。
# Python golden の find_flips() と bit-exact 比較。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/flip_calc.v
TOPLEVEL := flip_calc
MODULE   := test_flip_calc

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
