#include <iostream>
#if defined(_MSC_VER)
#include <intrin.h>
#else
#include <cpuid.h>
#include <immintrin.h>
#endif

int main() {
    unsigned a = 0, b = 0, c = 0, d = 0;
#if defined(_MSC_VER)
    int registers[4];
    __cpuidex(registers, 0, 0);
    if (registers[0] < 7)
        return 77;
    __cpuidex(registers, 1, 0);
    c = unsigned(registers[2]);
#else
    if (__get_cpuid_max(0, nullptr) < 7)
        return 77;
    __cpuid(1, a, b, c, d);
#endif
    if ((c & (1u << 27)) == 0 || (c & (1u << 28)) == 0) {
        std::cout << "OSXSAVE/AVX unavailable; AVX-512 runtime skipped\n";
        return 77;
    }
    const auto xcr0 = _xgetbv(0);
    if ((xcr0 & 0xe6) != 0xe6) {
        std::cout << "OS XCR0 lacks AVX-512 state; runtime skipped\n";
        return 77;
    }
#if defined(_MSC_VER)
    __cpuidex(registers, 7, 0);
    b = unsigned(registers[1]);
    c = unsigned(registers[2]);
#else
    __cpuid_count(7, 0, a, b, c, d);
#endif
    const unsigned avx512Mask = (1u << 16) | (1u << 17) | (1u << 28) | (1u << 30) | (1u << 31);
    const bool supported = (b & avx512Mask) == avx512Mask && (c & (1u << 11));
    std::cout << "AVX512F=" << bool(b & (1u << 16)) << " AVX512BW="
              << bool(b & (1u << 30)) << " AVX512VNNI=" << bool(c & (1u << 11))
              << " AVX512_DQ_CD_VL=" << bool((b & avx512Mask) == avx512Mask) << " XCR0=" << xcr0 << '\n';
    return supported ? 0 : 77;
}
