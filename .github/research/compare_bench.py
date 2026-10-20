"""Interleaved fixed-depth Stockfish benchmark; fail if node counts differ."""
import argparse
import json
import math
import pathlib
import re
import statistics
import subprocess


def bench(binary, depth):
    result = subprocess.run(
        [binary, "bench", "16", "1", str(depth), "default", "depth"],
        text=True, capture_output=True, check=True, timeout=180,
    )
    values = {}
    for label, key in [("Total time (ms)", "ms"), ("Nodes searched", "nodes")]:
        match = re.search(re.escape(label) + r"\s*:\s*(\d+)", result.stderr)
        if not match:
            raise RuntimeError(result.stderr[-2000:])
        values[key] = int(match[1])
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("candidate")
    parser.add_argument("output")
    parser.add_argument("--depth", type=int, default=14)
    parser.add_argument("--pairs", type=int, default=12)
    args = parser.parse_args()
    binaries = [str(pathlib.Path(x).resolve()) for x in [args.base, args.candidate]]
    for binary in binaries:
        bench(binary, args.depth)
    pairs = []
    for i in range(args.pairs):
        pair = {}
        for index in ([0, 1] if i % 2 == 0 else [1, 0]):
            pair["base" if index == 0 else "candidate"] = bench(binaries[index], args.depth)
        assert pair["base"]["nodes"] == pair["candidate"]["nodes"], pair
        pair["speedup_percent"] = 100 * (pair["base"]["ms"] / pair["candidate"]["ms"] - 1)
        pairs.append(pair)
        pathlib.Path(args.output).write_text(json.dumps({"depth": args.depth, "pairs": pairs}, indent=2) + "\n")
        print(json.dumps({"pair": i + 1, **pair}), flush=True)
    ratios = [math.log(p["base"]["ms"] / p["candidate"]["ms"]) for p in pairs]
    mean = statistics.mean(ratios)
    se = statistics.stdev(ratios) / math.sqrt(len(ratios))
    # Conservative approximate Student-t multiplier for 12 or more pairs.
    margin = 2.201 * se
    summary = {
        "geometric_speedup_percent": 100 * math.expm1(mean),
        "approx_95_percent_interval": [100 * math.expm1(mean - margin), 100 * math.expm1(mean + margin)],
    }
    pathlib.Path(args.output).write_text(json.dumps({"depth": args.depth, "binaries": binaries, "pairs": pairs, "summary": summary}, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
