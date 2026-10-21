"""Bounded seeded standard/Chess960 scenarios; check legal UCI bestmoves/PVs."""
import argparse
import json
from pathlib import Path
import random
import threading
import chess
import chess.engine

p=argparse.ArgumentParser()
p.add_argument('binary')
p.add_argument('output')
a=p.parse_args()
rng=random.Random(20261020)
positions=[]
for game in range(12):
    board=chess.Board() if game<6 else chess.Board.from_chess960_pos(rng.randrange(960))
    for ply in range(100):
        moves=list(board.legal_moves)
        if not moves or board.is_game_over():
            break
        captures=[m for m in moves if board.is_capture(m)]
        board.push(rng.choice(captures if captures and rng.random()<.5 else moves))
        if ply%7==0 and list(board.legal_moves):
            positions.append(board.copy())
for fen in [
 '4k3/1P6/8/8/8/8/6p1/4K3 w - - 0 1',
 'r3k2r/ppp2ppp/2n5/3pp3/3PP3/2N5/PPP2PPP/R3K2R w KQkq - 0 1',
 '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
 'r1b1k2r/1P3ppp/8/8/8/8/8/4K3 w kq - 0 1',
]:
    positions.append(chess.Board(fen))
assert len(positions)==180, len(positions)
engine=chess.engine.SimpleEngine.popen_uci(str(Path(a.binary).resolve()), timeout=30)
engine.configure({'Hash':16,'Threads':1})
timer=threading.Timer(180, engine.close)
timer.daemon=True
timer.start()
rows=[]
try:
    for index,board in enumerate(positions):
        assert board.is_valid(), board.fen()
        scenario=['depth8','nodes10000','multipv4','mate2_nodes10000'][index%4]
        limit=chess.engine.Limit(depth=8,nodes=20000)
        multipv=1
        if index%4==1:
            limit=chess.engine.Limit(nodes=10000)
        elif index%4==2:
            multipv=min(4,board.legal_moves.count())
        elif index%4==3:
            limit=chess.engine.Limit(mate=2,nodes=10000)
        with engine.analysis(board,limit,multipv=multipv,game=object()) as stream:
            best=stream.wait()
            infos=stream.multipv
        assert best.move in board.legal_moves, (index,scenario,board.fen(),best)
        checked=[]
        for info in infos:
            replay=board.copy()
            for move in info.get('pv',[]):
                assert move in replay.legal_moves, (index,scenario,board.fen(),move,info)
                replay.push(move)
            checked.append({'nodes':info.get('nodes'),'score':str(info.get('score')),
                            'pv':[move.uci() for move in info.get('pv',[])]})
        rows.append({'index':index,'scenario':scenario,'fen':board.fen(),
                     'chess960':board.chess960,'requested_multipv':multipv,
                     'bestmove':best.move.uci(),'legal':True,'infos':checked})
        Path(a.output).write_text(json.dumps({'seed':20261020,'results':rows},indent=2)+'\n')
        if (index+1)%30==0:
            print(f'{index+1}/180 scenarios legal',flush=True)
finally:
    timer.cancel()
    engine.quit()
assert len(rows)==180
print('PASS 180 seeded scenarios: legal bestmoves and every reported PV move.',flush=True)
