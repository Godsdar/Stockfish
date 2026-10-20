"""Deterministic cross-engine search comparison on seeded legal positions."""
import argparse
import json
import pathlib
import random
import chess
import chess.engine

p = argparse.ArgumentParser()
p.add_argument('base')
p.add_argument('candidate')
p.add_argument('output')
p.add_argument('--depth', type=int, default=8)
a = p.parse_args()
rng = random.Random(20261020)
positions = []
for game in range(12):
    board = chess.Board() if game < 6 else chess.Board.from_chess960_pos(rng.randrange(960))
    for ply in range(100):
        moves = list(board.legal_moves)
        if not moves or board.is_game_over():
            break
        # Sample actual legal games with some capture-rich lines.
        captures = [m for m in moves if board.is_capture(m)]
        move = rng.choice(captures if captures and rng.random() < .5 else moves)
        board.push(move)
        if ply % 7 == 0 and len(list(board.legal_moves)) > 0:
            positions.append(board.copy())
for fen in [
 '4k3/1P6/8/8/8/8/6p1/4K3 w - - 0 1',
 'r3k2r/ppp2ppp/2n5/3pp3/3PP3/2N5/PPP2PPP/R3K2R w KQkq - 0 1',
 '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
 'r1b1k2r/1P3ppp/8/8/8/8/8/4K3 w kq - 0 1',
]:
    positions.append(chess.Board(fen))
engines = [chess.engine.SimpleEngine.popen_uci(str(pathlib.Path(x).resolve())) for x in [a.base,a.candidate]]
results=[]
try:
    for engine in engines:
        engine.configure({'Hash':16,'Threads':1})
    for i,board in enumerate(positions):
        pair=[]
        for engine in engines:
            info=engine.analyse(board,chess.engine.Limit(depth=a.depth),game=object())
            pair.append({'nodes':info['nodes'],'score':str(info['score'].pov(chess.WHITE)),
                         'pv':[m.uci() for m in info.get('pv',[])]})
        result={'index':i,'fen':board.fen(),'chess960':board.chess960,'equal':pair[0]==pair[1],
                'base':pair[0],'candidate':pair[1]}
        results.append(result)
        if not result['equal']:
            raise AssertionError(result)
        if (i+1)%25==0:
            print(f'{i+1}/{len(positions)} identical',flush=True)
finally:
    for engine in engines:
        engine.quit()
    pathlib.Path(a.output).write_text(json.dumps({'seed':20261020,'depth':a.depth,'results':results},indent=2)+'\n')
print(f'All {len(positions)} positions identical: nodes, score, PV.',flush=True)
