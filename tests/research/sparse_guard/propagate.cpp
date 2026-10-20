#include <immintrin.h>
#include "nnue/layers/affine_transform_sparse_input.h"

using namespace Stockfish;
using namespace Stockfish::Eval::NNUE;
using Layer = Layers::AffineTransformSparseInput<1024, 32>;

extern "C" void sparse_propagate(const Layer* layer, const u8* input, i32* output,
                                  const NNZInfo<1024>* info) {
    layer->propagate(input, output, *info);
}
