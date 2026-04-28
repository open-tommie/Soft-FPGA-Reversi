// firmware/src/proto.h
//
// UART テキストプロトコル骨格 (etc/protocol.md 準拠)。
//
// 入力は LF 終端の ASCII 行。バッファ上限 (kLineMax) 内で 1 行を
// 組み立て、コマンド (2 文字大文字) + ペイロードに分解して処理する。
//
// 本ファイルは Pico SDK / Verilator に依存しない pure C++17 として
// ホスト側でも単体ビルドできるように作る。出力は emit() 関数ポインタを
// 渡してもらうコールバック方式。

#ifndef SFR_PROTO_H
#define SFR_PROTO_H

#include <cstddef>
#include <cstdint>

namespace sfr::proto {

constexpr std::size_t kLineMax = 256;
constexpr const char* kVersion = "VE01reversi-fw";  // VE 応答

// 出力 1 行を送るコールバック (改行は付けないで渡す。実装側が "\n" を付与)
using EmitFn = void (*)(const char* line, std::size_t len);

class Parser {
public:
    explicit Parser(EmitFn emit) : emit_(emit) {}

    // 1 バイト投入。LF を受けたら行を解釈して emit_() を呼ぶ。
    // CR / 非 ASCII / 行長超過などはエラー応答 (ER0n) を返して破棄。
    void feed_byte(uint8_t b);

    // テスト用に内部状態をリセット
    void reset();

private:
    void handle_line();
    void emit_line(const char* s);              // null-terminated
    void emit_line(const char* s, std::size_t n);

    EmitFn emit_;
    char buf_[kLineMax]{};
    std::size_t len_ = 0;
    bool overflow_ = false;
};

}  // namespace sfr::proto

#endif  // SFR_PROTO_H
