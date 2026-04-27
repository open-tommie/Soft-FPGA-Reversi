//
// stub_mutex.h
// シングルスレッド環境向けのmutexおよび関連スタブ実装
// Verilatorのマルチスレッド機能を使用しない場合に利用
// 
// Last updated on: Oct-31-2025
// by tommie.jp (GitHub: open-tommie)
//
// SPDX-License-Identifier: MIT
// 

#ifndef STUB_MUTEX_H
#define STUB_MUTEX_H

// 参考実装の verilated.cpp は debug.h の _DEBUG() マクロを呼ぶ。
// 当方は debug.h を持ち込まないので no-op にする。
#ifndef _DEBUG
#  define _DEBUG(...) ((void)0)
#endif

namespace std {
    class mutex {
    public:
        mutex() = default;
        ~mutex() = default;
        void lock() {}          // No-op: シングルスレッド
        bool try_lock() { return true; }
        void unlock() {}        // No-op
    };

    // VerilatedMutexのtypedef (Verilator互換)
    using VerilatedMutex = mutex;

    // unique_lockの前方宣言 (後で<mutex>が定義)
    template <typename Mutex> class unique_lock;

    class condition_variable_any {
    public:
        condition_variable_any() = default;
        ~condition_variable_any() = default;

        // 標準: unique_lock版 (前方宣言でOK、no-op)
        void wait(unique_lock<mutex>&) {}  // No-op

        // Verilator非標準: 直接mutex版
        void wait(mutex& m) { /* No-op: シングルスレッドなので待機せず */ }

        template <typename Pred>
        bool wait(unique_lock<mutex>&, Pred pred) { return pred(); }  // 条件即時評価

        void notify_one() {}
        void notify_all() {}
    };
}

// std定義後にverilated.hをインクルード (mutex/time使用可能)
#include "verilated.h"

// POSIX timeスタブ (SDKのclockid_t/timespec使用、verilated.h後で型完全確保)
#define CLOCK_PROCESS_CPUTIME_ID 2  // POSIX標準値 (SDK未定義なので定義、Linux互換)
#define CLOCK_MONOTONIC 1           // POSIX標準値 (SDK未定義なので定義、Linux互換)

inline int clock_gettime(clockid_t clk_id, struct timespec *tp) {
    if (clk_id == CLOCK_PROCESS_CPUTIME_ID || clk_id == CLOCK_MONOTONIC) {
        tp->tv_sec = 0;
        tp->tv_nsec = 0;
        return 0;  // 成功: 0.0秒を返す (no-op)
    }
    return -1;  // サポート外クロックID
}

// VlThreadPoolの最小スタブ (シングルスレッド用: no-op, デフォルトベースコンストラクタ)
class VlThreadPool : public VerilatedVirtualBase {
public:
    VlThreadPool(VerilatedContext* contextp, unsigned nThreads)
        : VerilatedVirtualBase() {}  // デフォルトベースコンストラクタ呼び出し (contextp不要)

    ~VlThreadPool() override = default;  // 仮想デストラクタ
    // 追加メソッド不要: シングルスレッドでプール使用なし
};

#endif  // STUB_MUTEX_H