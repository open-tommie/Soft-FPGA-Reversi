// firmware/src/stub_mutex.h
//
// Verilator のホスト前提機能 (マルチスレッド / トレース / mutex / 時刻) を
// 組込み (Pico 2 / Cortex-M33 単一スレッド) で殺すための stub。
// 上流 (verilator install 同梱の) verilated.cpp を **無修正のまま** リンクできる
// ように、verilated_threads.h / verilated_trace.h の include guard を
// 先取り定義し、それぞれが提供すべき型を最小実装で差し込む。
//
// 対象 Verilator: 5.048
// Verilator を上げた場合は本ファイル冒頭のテーブルを更新し、必要なら追加 stub
// が要るかを確認すること:
//   - verilated.cpp が verilated_threads.h / verilated_trace.h から
//     どのシンボルを参照しているかを grep し直す
//   - 参照されているメソッドがここに揃っているかチェック

#ifndef SFR_STUB_MUTEX_H
#define SFR_STUB_MUTEX_H

#include <time.h>

// ----- std::mutex / condition_variable_any (シングルスレッド向け no-op) -----
namespace std {

class mutex {
public:
    mutex() = default;
    ~mutex() = default;
    void lock() {}
    bool try_lock() { return true; }
    void unlock() {}
};

}  // namespace std

// verilated_threads.h と verilated_trace.h は std::thread / std::condition_variable
// をはじめ多くのホスト依存を引き連れて来る。include guard を先取りして
// 取り込みごと潰し、必要な型は下で前方宣言する。
#define VERILATOR_VERILATED_THREADS_H_
#define VERILATOR_VERILATED_TRACE_H_

// VerilatedVirtualBase など verilated.h 由来の型を確定させる。
#include "verilated.h"

// ----- verilated.cpp が verilated_threads.h から要求する型 -----
// 5.048 時点では VlThreadPool のみ。コンストラクタは m_threads > 1 でしか
// 到達しないが、コンパイル成立には型定義が必要。
class VlThreadPool : public VerilatedVirtualBase {
public:
    VlThreadPool(VerilatedContext*, unsigned) {}
    ~VlThreadPool() override = default;
};

// ----- verilated.cpp が verilated_trace.h から要求する型 -----
// 5.048 時点で実体呼ばれは isOpen() / modelConnected(getter/setter)。
// 当方は --no-trace でトレース未生成なので runtime に到達しない。
class VerilatedTraceBaseC {
public:
    bool isOpen() const { return false; }
    bool modelConnected() const { return false; }
    void modelConnected(bool) {}
};

class VerilatedTraceConfig {};

// ----- newlib に欠ける CLOCK_* と clock_gettime() -----
#ifndef CLOCK_MONOTONIC
#  define CLOCK_MONOTONIC 1
#endif
#ifndef CLOCK_PROCESS_CPUTIME_ID
#  define CLOCK_PROCESS_CPUTIME_ID 2
#endif

inline int clock_gettime(clockid_t /*clk_id*/, struct timespec* tp) {
    tp->tv_sec = 0;
    tp->tv_nsec = 0;
    return 0;
}

#endif  // SFR_STUB_MUTEX_H
