# Native evidence for independent OptionsMap insertion order

Source base: `effdc3fd3f6de6e75fe1374a51a7a7eed66f880b`.
Source candidate: `e6c3a5fba865c1d56fadf7cf607ae080547d620c`.
Validation harness: `c9c617d75cae5f0f2e8e481f0e4178e20d8b4548`.
[Original run 39555359933](https://github.com/Godsdar/Stockfish/actions/runs/39555359933).

The candidate only changes OptionsMap insertion-index bookkeeping and adds the author's existing name entry. Search behavior is unchanged. The baseline and candidate both pass bench1559611,75 upstream tests and180 seeded standard/Chess960 scenarios on native Windows/MSVC AVX2 release and Linux/GCC AVX2 release.

`fixture-results.json` preserves18 native regression invocations per platform:8 standalone scenarios and one real two-Engine integration fixture for each source. Expected baseline failures have exit1; they are not CI failures. The duplicate-option control deliberately exits1 on both versions. The candidate passes all other scenarios. Real engine enumeration is19+0 options on baseline,19+19 on the candidate; no engine search occurs in these fixtures.

This evidence directory contains text/JSON/source identities and raw build/test output only. Executables, objects and the embedded NNUE payload are omitted. Original run/job logs remain available. The initial Linux artifact included NNUE-embedded fixture executables unnecessarily; this lightweight immutable evidence commit preserves its useful content and the oversized artifact was deleted after byte-for-byte verification, without rerunning validation. Future workflow upload rules explicitly exclude executables/objects and use7-day retention.

The fix does not assert general multi-instance engine/thread/tablebase support. Same-map concurrent mutation and the separate combo duplicate-var problem are out of scope. No Elo, speed or security claim is made.

The macOS Apple Silicon candidate was also built with the standard Makefile, Clang, the Xcode SDK, release `-O3 -DNDEBUG` and `-Werror` (`-j2`). Bench1559611,75 upstream tests and180 standard/Chess960 scenarios pass. `options-macos-arm64/` preserves the full build/test logs, command/environment record, binary hash and earlier baseline/fixed standalone and real Engine fixture results. The full macOS run tests only the candidate; paired baseline/fixed full-engine comparisons are preserved for Windows and Linux.
