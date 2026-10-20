"""Compile the actual before/after LUT access as a constant expression."""
import pathlib
import subprocess
import sys
import os
base, candidate, output = map(lambda p: pathlib.Path(p).resolve(), sys.argv[1:])
output.mkdir(exist_ok=True)
old_source = (base/'src/nnue/features/full_threats.cpp').read_text()
a=old_source.index('constexpr auto init_index_luts()')
b=old_source.index('// The final index', a)
reference=old_source[a:b].replace('init_index_luts', 'reference_index_luts')
for label, repo in [('before',base),('after',candidate)]:
    pointer='&threat_luts.lut1[0][0]' if label=='before' else 'threat_luts.lut1.data()'
    expected='threat_luts.lut1[W_PAWN][B_KNIGHT][0]' if label=='before' else 'threat_luts.lut1[W_PAWN * PIECE_NB + B_KNIGHT][0]'
    checks=''
    if label=='after':
        checks=reference+'''
constexpr bool all_pairs_match() {
    const auto reference = reference_index_luts();
    for (int a = 0; a < PIECE_NB; ++a)
        for (int b = 0; b < PIECE_NB; ++b)
            for (int side = 0; side < 2; ++side)
                if (reference[a][b][side] != threat_luts.lut1[a * PIECE_NB + b][side])
                    return false;
    return true;
}
static_assert(all_pairs_match());
'''
    source=f'''#include "{(repo/'src/nnue/features/full_threats.cpp').as_posix()}"
namespace Stockfish::Eval::NNUE::Features {{
constexpr u32 check_flat_index() {{
    const auto* lut1_flat = {pointer};
    return lut1_flat[(W_PAWN << 4) | B_KNIGHT][0];
}}
static_assert(check_flat_index() == {expected});
{checks}
}}
'''
    cpp=output/f'{label}.cpp'
    cpp.write_text(source)
    if os.name=='nt':
        command=['cl','/nologo','/std:c++17','/EHsc','/c','/constexpr:steps500000000',str(cpp),f'/Fo{output/label}.obj']
    else:
        command=['g++','-std=c++17','-fsyntax-only','-fconstexpr-ops-limit=500000000',str(cpp)]
    result=subprocess.run(command,capture_output=True,text=True)
    (output/f'{label}-compile.log').write_text(result.stdout+result.stderr)
    print(label,'compiler return code:',result.returncode)
    print(result.stdout+result.stderr)
    if (result.returncode != 0) != (label=='before'):
        raise AssertionError(f'Unexpected {label} compile result')
