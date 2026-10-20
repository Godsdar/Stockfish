#include <immintrin.h>
#include <array>
#include <iostream>
#include <memory>
#include <sstream>
#include "nnue/layers/affine_transform_sparse_input.h"

using namespace Stockfish;
using namespace Stockfish::Eval::NNUE;
using Layer = Layers::AffineTransformSparseInput<1024, 32>;

int main() {
    auto layer = std::make_unique<Layer>();
    std::stringstream stream(std::ios::in | std::ios::out | std::ios::binary);
    std::array<i32, 32> biases{};
    std::array<std::array<i8, 1024>, 32> weights{};
    for (int o = 0; o < 32; ++o) {
        biases[o] = o * 13 - 1000;
        write_little_endian(stream, biases[o]);
    }
    for (int o = 0; o < 32; ++o)
        for (int i = 0; i < 1024; ++i) {
            weights[o][i] = i8((o * 29 + i * 3) % 31 - 15);
            write_little_endian(stream, weights[o][i]);
        }
    stream.seekg(0);
    if (!layer->read_parameters(stream))
        return 2;

    unsigned cases = 0;
    for (unsigned count = 0; count <= 256; ++count)
        for (unsigned permutation : {1u, 73u}) {
            alignas(64) std::array<u8, 1024> input{};
            alignas(64) Layer::OutputBuffer output{};
            NNZInfo<1024> info{};
            info.count = count;
            for (unsigned k = 0; k < count; ++k) {
                const unsigned chunk = (k * permutation) % 256;
                info.nnz[k] = u16(chunk);
                for (unsigned b = 0; b < 4; ++b)
                    input[chunk * 4 + b] = u8((chunk * 7 + b * 17) % 127 + 1);
            }
            layer->propagate(input.data(), output, info);
            for (unsigned o = 0; o < 32; ++o) {
                i32 expected = biases[o];
                for (unsigned i = 0; i < 1024; ++i)
                    expected += i32(weights[o][i]) * input[i];
                if (output[o] != expected) {
                    std::cerr << "Mismatch count=" << count << " permutation=" << permutation
                              << " output=" << o << " actual=" << output[o]
                              << " expected=" << expected << '\n';
                    return 1;
                }
            }
            ++cases;
        }
    std::cout << cases << " layer cases passed (counts 0..256, two index orders)\n";
}
