"""Make a sparse all-zero SFNNv18 network while retaining valid format hashes.

This is a diagnostic fixture, not a chess-strength network. It deliberately
exercises zero sparse activation chunks; no default-network occurrence is claimed.
"""
from pathlib import Path
import struct
import sys

source, output = [Path(x).resolve() for x in sys.argv[1:3]]
ft_bytes = (45056 + 59808 + 4560) * 1024 + 1024 * 2
stack_bytes = 32 * 4 + 1024 * 32 + 32 * 4 + 64 * 32 + 4 + 128
with source.open('rb') as stream:
    header = stream.read(12)
    version, net_hash, description_size = struct.unpack('<III', header)
    assert version == 0x6A448AFA
    description = stream.read(description_size)
    ft_hash = stream.read(4)
    ft_start = stream.tell()
    stack_start = ft_start + ft_bytes
    assert source.stat().st_size == stack_start + 32 * (stack_bytes + 4)
    stack_hashes = []
    for i in range(32):
        stream.seek(stack_start + i * (stack_bytes + 4))
        stack_hashes.append(stream.read(4))
    assert len(set(stack_hashes)) == 1
with output.open('wb') as stream:
    stream.write(header + description + ft_hash)
    for i, stack_hash in enumerate(stack_hashes):
        stream.seek(stack_start + i * (stack_bytes + 4))
        stream.write(stack_hash)
    stream.truncate(source.stat().st_size)
print(f'Created all-zero diagnostic network: {output} ({output.stat().st_size} bytes)')
