#include "codegen.cpp"
#include <cstdint>
#include <cstdio>

int main() {
    alignas(64) int8_t removed[sizeof(V)], added[sizeof(V)];
    alignas(64) int16_t accumulator[sizeof(V)], baseline[sizeof(V)], candidate[sizeof(V)];
    unsigned pairs = 0;
    for (int r = -128; r <= 127; ++r)
        for (int a = -128; a <= 127; ++a)
        {
            for (unsigned lane = 0; lane < sizeof(V); ++lane)
            {
                // Distinct lane values exercise unpack order; across the outer loops
                // every byte lane sees all 65,536 combinations.
                removed[lane] = int8_t(uint8_t(r + int(lane)));
                added[lane] = int8_t(uint8_t(a - int(lane)));
                accumulator[lane] = int16_t(uint16_t(lane * 12347 + pairs));
            }
            original(reinterpret_cast<V*>(baseline), reinterpret_cast<const V*>(accumulator),
                     reinterpret_cast<const V*>(removed), reinterpret_cast<const V*>(added));
            mixed(reinterpret_cast<V*>(candidate), reinterpret_cast<const V*>(accumulator),
                  reinterpret_cast<const V*>(removed), reinterpret_cast<const V*>(added));
            for (unsigned lane = 0; lane < sizeof(V); ++lane)
                if (candidate[lane] != baseline[lane])
                {
                    std::printf("Mismatch r=%d a=%d lane=%u\n", r, a, lane);
                    return 1;
                }
            ++pairs;
        }
    std::printf("PASS %u pairs across %zu int16 lanes\n", pairs, sizeof(V));
}
