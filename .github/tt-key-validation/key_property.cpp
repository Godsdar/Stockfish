// GPLv3: a standalone validation harness using Stockfish's production Position.
#include <algorithm>
#include <array>
#include <cstring>
#include <deque>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "attacks.h"
#include "position.h"
#include "movegen.h"
using namespace Stockfish;

static void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
static bool fast(const Position& p, Move m) {
    return m.type_of() == NORMAL && type_of(p.moved_piece(m)) != PAWN
        && !p.can_castle(ANY_CASTLING) && p.ep_square() == SQ_NONE;
}
static std::vector<Move> legal_moves(const Position& p) {
    std::vector<Move> out;
    for (Move m : MoveList<ALL>(p)) if (p.legal(m)) out.push_back(m);
    std::sort(out.begin(),out.end(),[](Move a,Move b){return a.raw()<b.raw();});
    return out;
}
static std::string snapshot(const Position& p) {
    std::ostringstream s;
    s << p.fen() << ':' << p.key() << ':' << p.material_key() << ':' << p.pawn_key()
      << ':' << p.minor_piece_key() << ':' << p.game_ply() << ':' << p.is_chess960()
      << ':' << p.checkers() << ':' << p.pieces() << ':' << p.state();
    for (Color c : {WHITE,BLACK}) {
        s << ':' << p.pieces(c) << ':' << p.non_pawn_key(c) << ':' << p.non_pawn_material(c)
          << ':' << p.blockers_for_king(c) << ':' << p.pinners(c)
          << ':' << p.count<ALL_PIECES>(c) << ':' << p.count<PAWN>(c) << ':' << p.count<KNIGHT>(c)
          << ':' << p.count<BISHOP>(c) << ':' << p.count<ROOK>(c) << ':' << p.count<QUEEN>(c) << ':' << p.count<KING>(c);
    }
    for (int pt=PAWN;pt<=KING;++pt)
        s << ':' << p.pieces(PieceType(pt)) << ':' << p.check_squares(PieceType(pt)) << ':' << p.threats_by(PieceType(pt));
    for (Piece pc:p.piece_array()) s << ':' << int(pc);
    for (Move m:legal_moves(p)) s << ':' << m.raw();
    return s.str();
}
struct Counts {
    unsigned long long positions=0,moves=0,fastMoves=0,fastCaptures=0,fastQuiets=0;
    unsigned long long excludedSpecial=0,excludedPawn=0,excludedRights=0,excludedEP=0,historyPositions=0;
} counts;
static void check(Position& p, bool history=false) {
    ++counts.positions; counts.historyPositions+=history;
    const std::string before=snapshot(p);
    // Snapshot each live history object separately, preserving padding exactly as observed.
    std::vector<std::pair<StateInfo*,std::array<unsigned char,sizeof(StateInfo)>>> states;
    for (StateInfo* st=p.state();st;st=st->previous) {
        states.emplace_back();states.back().first=st;
        std::memcpy(states.back().second.data(),st,sizeof(StateInfo));
    }
    for (Move m:legal_moves(p)) {
        ++counts.moves;
        bool special=m.type_of()!=NORMAL,pawn=type_of(p.moved_piece(m))==PAWN;
        bool rights=p.can_castle(ANY_CASTLING),ep=p.ep_square()!=SQ_NONE;
        bool useFast=fast(p,m);
        require(useFast==!(special||pawn||rights||ep),"guard mismatch");
        counts.excludedSpecial+=special;counts.excludedPawn+=pawn;counts.excludedRights+=rights;counts.excludedEP+=ep;
        Key candidate=0;
        if(useFast) {
            ++counts.fastMoves;
            if(p.capture(m))++counts.fastCaptures;else ++counts.fastQuiets;
            candidate=p.prefetch_key(m);
            require(snapshot(p)==before,"prefetch_key changed Position");
        }
        StateInfo child{};
        p.do_move(m,child);
        Key actual=p.key();
        // When excluded, the candidate intentionally uses this original fallback.
        if(!useFast)candidate=actual;
        require(candidate==actual,"child key mismatch");
        p.undo_move(m);
        require(snapshot(p)==before,"do/undo changed parent public state");
        for(const auto& saved:states)
            require(std::memcmp(saved.first,saved.second.data(),sizeof(StateInfo))==0,"do/undo changed live StateInfo history bytes");
        require(p.pos_is_ok()&&p.material_key_is_ok(),"invalid restored position");
    }
}
int main(int argc,char**argv) {
    try {
        require(argc==2,"usage: key_property property-corpus.tsv");
        Attacks::init();Position::init();
        std::ifstream in(argv[1]);require(bool(in),"corpus open failed");
        std::string line;
        while(std::getline(in,line)) {
            auto tab=line.find('\t');require(tab!=std::string::npos,"bad corpus line");
            Position p;StateInfo st{};
            auto err=p.set(line.substr(tab+1),line.substr(0,tab)=="1",&st);
            if(err)throw *err;
            check(p);
        }
        // Preserve actual prior-state chains, including reversible moves, during checks.
        for(unsigned game=0;game<16;++game) {
            std::deque<StateInfo> history(1);Position p;
            auto err=p.set("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",false,&history.back());
            if(err)throw *err;
            unsigned long long random=2026102113ULL+game;
            for(unsigned ply=0;ply<128;++ply) {
                if(ply%8==0)check(p,ply>0);
                auto moves=legal_moves(p);if(moves.empty())break;
                random^=random<<13;random^=random>>7;random^=random<<17;
                Move m=moves[random%moves.size()];history.emplace_back();p.do_move(m,history.back());
            }
        }
        require(counts.fastMoves&&counts.fastCaptures&&counts.fastQuiets,"missing fast-path coverage");
        require(counts.excludedSpecial&&counts.excludedPawn&&counts.excludedRights&&counts.excludedEP&&counts.historyPositions,"missing exclusion/history coverage");
        std::cout << "{\"positions\":" << counts.positions << ",\"legal_moves\":" << counts.moves
          << ",\"fast\":" << counts.fastMoves << ",\"fast_captures\":" << counts.fastCaptures
          << ",\"fast_quiets\":" << counts.fastQuiets << ",\"excluded_special\":" << counts.excludedSpecial
          << ",\"excluded_pawn\":" << counts.excludedPawn << ",\"excluded_rights\":" << counts.excludedRights
          << ",\"excluded_ep\":" << counts.excludedEP << ",\"history_positions\":" << counts.historyPositions << ",\"pass\":true}\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<"PROPERTY FAILURE: "<<e.what()<<'\n';return 1;}
}
