# Mixed-sign NNUE row experiment validation

Candidate source is **939c57d819aa715aec1c26224ad204ed50ec8fa8** on
`Godsdar/Stockfish:experiment/mixed-sign-rows`. Baseline is
**effdc3fd3f6de6e75fe1374a51a7a7eed66f880b**, official master at session start.
The workflow checks these immutable source commits in separate directories;
this CI branch adds validation scripts only.

`source.patch` is the exact candidate diff. `codegen.cpp` implements the original
two single-row arithmetic and proposed mixed arithmetic with matching intrinsics.
`runtime-check.cpp` compares all 65,536 signed-byte pairs at each vector lane,
with varying accumulator wraparound values. AVX2 is executed; AVX512 is compiled
without assuming runner support. Full engines are built in AVX2 and AVX512VNNI;
the latter is compile-only.

`compare_search.py` is copied without modification from the preceding research
session's deterministic seed-20261020, standard/Chess960 depth-8 comparison.
`build_windows.py` derives from the coordinating session's MSVC builder, adding
release assertions settings and an AVX512 build mode. `compare_bench.py` derives
from the coordinating session's alternating benchmark script, adding complete
stdout/stderr retention and explicit pair order. Only sequential processes run
within a runner during timing. All builds use the same downloaded network bytes.

Results record CPU, compiler, commit bindings, network SHA256, source patch,
script SHA256 manifest, signatures, upstream suite, search comparisons, every
timed invocation and raw JSON. Hosted-runner timing is screening evidence;
identical nodes and a local NPS gain do not establish playing strength or Elo.
No upstream PR is created by this workflow.

A separate `research/mixed-pair-avx512` branch executes AVX512VNNI only after
a baseline-ISA CPUID/XGETBV probe confirms CPU features and OS ZMM state.
That run keeps AVX2 results separate, checks the same immutable source commits,
and repeats the arithmetic harness, signatures, suite, deterministic positions
and sequential paired timing under the AVX512VNNI build. Unsupported runners
retain compile-only evidence and skip execution. The probe derives from the
architecture subagent's sparse-guard validation, extended for full-engine flags.
