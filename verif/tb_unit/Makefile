# 各 RTL モジュールごとの cocotb サブディレクトリを順に回す top-level wrapper。
# scripts/test-unit.sh から呼び出される。

SUBDIRS := proto legal_bb coord pick_lsb game_state

.PHONY: all clean $(SUBDIRS)

all: $(SUBDIRS)

$(SUBDIRS):
	@echo "============================================================"
	@echo "  cocotb: $@"
	@echo "============================================================"
	$(MAKE) -C $@ $(MAKECMDGOALS)

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
