#include <immintrin.h>

#if defined(EXPECT_AVX512) || defined(__AVX512BW__)
using V = __m512i;
#define LOAD _mm512_load_si512
#define STORE _mm512_store_si512
#define ZERO _mm512_setzero_si512
#define ULO _mm512_unpacklo_epi8
#define UHI _mm512_unpackhi_epi8
#define SRA _mm512_srai_epi16
#define ADD _mm512_add_epi16
#define SUB _mm512_sub_epi16
#define XOR _mm512_xor_si512
#define BCAST8 _mm512_set1_epi8
#define BCAST16 _mm512_set1_epi16
#define MADD _mm512_maddubs_epi16
#else
using V = __m256i;
#define LOAD _mm256_load_si256
#define STORE _mm256_store_si256
#define ZERO _mm256_setzero_si256
#define ULO _mm256_unpacklo_epi8
#define UHI _mm256_unpackhi_epi8
#define SRA _mm256_srai_epi16
#define ADD _mm256_add_epi16
#define SUB _mm256_sub_epi16
#define XOR _mm256_xor_si256
#define BCAST8 _mm256_set1_epi8
#define BCAST16 _mm256_set1_epi16
#define MADD _mm256_maddubs_epi16
#endif

extern "C" void original(V* output, const V* acc, const V* removed, const V* added) {
    V r = LOAD(removed), a = LOAD(added), zero = ZERO();
    V rlo = SRA(ULO(zero, r), 8), rhi = SRA(UHI(zero, r), 8);
    V alo = SRA(ULO(zero, a), 8), ahi = SRA(UHI(zero, a), 8);
    STORE(output, ADD(SUB(LOAD(acc), rlo), alo));
    STORE(output + 1, ADD(SUB(LOAD(acc + 1), rhi), ahi));
}

extern "C" void mixed(V* output, const V* acc, const V* removed, const V* added) {
    const V offset = BCAST8(-128), signs = BCAST16(0x01ff);
    V r = XOR(LOAD(removed), offset), a = XOR(LOAD(added), offset);
    V lo = MADD(ULO(r, a), signs), hi = MADD(UHI(r, a), signs);
    STORE(output, ADD(LOAD(acc), lo));
    STORE(output + 1, ADD(LOAD(acc + 1), hi));
}
