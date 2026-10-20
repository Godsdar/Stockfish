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
    if ((c & (1u << 23)) == 0) {
        std::cout << "POPCNT unavailable; runtime skipped\n";
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
    // Full engines use AVX2/BMI/POPCNT plus the AVX512F/DQ/CD/BW/VL/VNNI suite.
    const unsigned required_b = (1u << 3) | (1u << 5) | (1u << 16) | (1u << 17)
                              | (1u << 28) | (1u << 30) | (1u << 31);
    const bool supported = (b & required_b) == required_b && (c & (1u << 11));
    std::cout << "AVX2=" << bool(b & (1u << 5)) << " BMI1=" << bool(b & (1u << 3))
              << " AVX512DQ=" << bool(b & (1u << 17)) << " AVX512CD=" << bool(b & (1u << 28))
              << " AVX512VL=" << bool(b & (1u << 31)) << " AVX512F=" << bool(b & (1u << 16)) << " AVX512BW="
              << bool(b & (1u << 30)) << " AVX512VNNI=" << bool(c & (1u << 11))
              << " XCR0=" << xcr0 << '\n';
    return supported ? 0 : 77;
}
