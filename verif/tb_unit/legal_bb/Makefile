# cocotb で rtl/legal_bb.v を直接 toplevel として検証する。
# verif/golden/reversi_rules.py を bit-exact 比較の唯一の golden とする。

TOPLEVEL_LANG = verilog
SIM ?= verilator

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../../..)
RTL_DIR   := $(REPO_ROOT)/rtl

VERILOG_SOURCES := $(RTL_DIR)/legal_bb.v
TOPLEVEL := legal_bb
MODULE   := test_legal_bb

EXTRA_ARGS += --no-timing -Wno-fatal

include $(shell cocotb-config --makefiles)/Makefile.sim
