// firmware/src/cxx_minimal.cpp
//
// 組込み (Pico 2 / 単一スレッド) では C++ 例外も RTTI ベースの動的型情報も
// 使わないが、libstdc++ / libsupc++ の一部関数は libstdc++ 内部で例外を
// 投げる側の参照があり、リンカが personality routine と __cxa_throw_*
// を引き連れて来る。さらに personality routine は libstdc++ の
// **C++ name demangler** (cp-demangle.c, ~15 KiB) を引き連れる。
//
// ここで personality / pure-virtual / throw を **abort 等価の stub** で
// 用意し、libsupc++ の本物が引かれない/上書きされるようにする。
//
// 仮にここに到達したら何かが throw した == 設計違反。`__builtin_trap` で
// 即停止する。Cortex-M33 では BKPT 命令になるので Debug Probe で観測可能。

#include <cstddef>

extern "C" {

[[noreturn]] void __gxx_personality_v0() { __builtin_trap(); }
[[noreturn]] void __cxa_pure_virtual()    { __builtin_trap(); }

// libstdc++ の "throw bad_alloc" などが参照する関数群を stub にして
// 本物 (例外オブジェクト構築 + unwind) を引かないようにする。
[[noreturn]] void __cxa_throw_bad_array_new_length() { __builtin_trap(); }

// __cxa_demangle は libstdc++ の cp-demangle.c (~15 KiB) のエントリ。
// これを stub で先に提供すると、demangler 本体の翻訳ユニット全体が
// リンクされなくなる (d_print_comp_inner / d_type / d_name 等が消える)。
// uncaught exception のときに型名が "??" になるだけで実害ない。
char* __cxa_demangle(const char* /*mangled_name*/, char* /*output_buffer*/,
                     std::size_t* /*length*/, int* status) {
    if (status) *status = -1;  // -1 = memory allocation failure (定義済み)
    return nullptr;
}

}  // extern "C"
