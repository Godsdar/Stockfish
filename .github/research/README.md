# Frozen functional search candidate validation

Baseline/source network: effdc3fd3f6de6e75fe1374a51a7a7eed66f880b.

- S1: 035bf5920391d467fedd7b6af63a8942ab6ee720, damp applied correction by rule50;
  expected default signature 1640333.
- S2: b983b697193530c234514fa337be42dabfe3ddef, exclude restricted fail-low
  correction targets; expected default signature 2450249.

All source refs are immutable. This CI branch only adds validation, with no
source modifications to either candidate. Native Windows/MSVC and Linux/GCC
release AVX2 builds use NDEBUG and identical network bytes. The baseline is
checked out for network/provenance only; this job is not a game or speed test.

Each candidate runs the 75 upstream instrumented tests and a seeded 180-position
standard/Chess960 scenario suite. Position generation is copied from the previous
research session's seed-20261020 deterministic comparison, with unchanged
positions. The scenarios cycle through bounded depth 8 (max 20k nodes), 10k nodes,
MultiPV up to 4 (depth 8/max 20k nodes), and mate 2/max 10k nodes. Every returned
bestmove and every move of every reported PV must be legal. A per-engine
180-second watchdog closes a stuck owned engine; the job has a 35-minute cap.

Search results are expected to differ from baseline. No equality-to-baseline,
NPS improvement, playing strength, Elo, Fishtest or upstream acceptance is
claimed. Both candidates require independent game/mate/regression investigation.
Results retain commit bindings, source patches, CPU/compiler, command logs,
network SHA256, suite output, scenario details and a script SHA256 manifest.
