// firmware/src/proto.cpp
//
// UART テキストプロトコル パーサ。Bootstrap step 3 (PI/VE) の最小実装。
// MO/PA/BO/EB/EW/ED は受け付けるが「未実装」として ER02 を返す。

#include "proto.h"

#include <cstring>

namespace sfr::proto {

namespace {

bool is_upper_ascii(char c) {
    return c >= 'A' && c <= 'Z';
}

bool is_known_cmd2(const char* p) {
    static constexpr const char* kKnown[] = {
        "PI", "VE", "SB", "SW", "MO", "PA", "BO", "EB", "EW", "ED",
    };
    for (const char* k : kKnown) {
        if (p[0] == k[0] && p[1] == k[1]) return true;
    }
    return false;
}

}  // namespace

void Parser::reset() {
    len_ = 0;
    overflow_ = false;
}

void Parser::emit_line(const char* s) {
    emit_line(s, std::strlen(s));
}

void Parser::emit_line(const char* s, std::size_t n) {
    if (emit_) emit_(s, n);
}

void Parser::feed_byte(uint8_t b) {
    if (b == '\n') {
        if (overflow_) {
            emit_line("ER02 line too long");
            reset();
            return;
        }
        handle_line();
        reset();
        return;
    }
    if (b == '\r') {
        // protocol.md §4: CR 混入は ER03
        emit_line("ER03 CR not allowed");
        // 行は破棄。続く LF も破棄したい所だが状態管理を簡単に保つため
        // overflow_ フラグを再利用して次の LF まで吸収させる。
        overflow_ = true;
        return;
    }
    if (b > 0x7E) {
        emit_line("ER02 non-ascii");
        overflow_ = true;
        return;
    }
    if (len_ >= kLineMax - 1) {
        // バッファ満杯。LF までは読み続けるが overflow_ フラグを立てる。
        overflow_ = true;
        return;
    }
    buf_[len_++] = static_cast<char>(b);
}

void Parser::handle_line() {
    if (len_ < 2) {
        emit_line("ER02 short");
        return;
    }
    if (!is_upper_ascii(buf_[0]) || !is_upper_ascii(buf_[1])) {
        emit_line("ER02 bad cmd");
        return;
    }
    if (!is_known_cmd2(buf_)) {
        emit_line("ER02 unknown cmd");
        return;
    }

    // PI: payload なし
    if (buf_[0] == 'P' && buf_[1] == 'I') {
        if (len_ != 2) {
            emit_line("ER04 PI no args");
            return;
        }
        emit_line("PO");
        return;
    }

    // VE: payload なし → "VE01<name>" を返す
    if (buf_[0] == 'V' && buf_[1] == 'E') {
        if (len_ != 2) {
            emit_line("ER04 VE no args");
            return;
        }
        emit_line(kVersion);
        return;
    }

    // 既知コマンドだが未実装。骨格段階では ER02 で拒否。
    emit_line("ER02 not implemented");
}

}  // namespace sfr::proto
