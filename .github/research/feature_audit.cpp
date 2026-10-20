// Research harness for Stockfish NNUE feature invariants. GPL-3.0-or-later.
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <string>
#include <vector>
#include "attacks.h"
#include "movegen.h"
#include "position.h"
#include "nnue/features/full_threats.h"
#include "nnue/features/pp_3wide.h"
#include "nnue/features/k32q2.h"

using namespace Stockfish;
using namespace Stockfish::Eval::NNUE::Features;
using Bag = std::map<unsigned, int>;

template<class List> Bag bag(const List& l) {
    Bag b;
    for (auto i : l) ++b[i];
    return b;
}
template<class List> void adjust(Bag& b, const List& l, int sign) {
    for (auto i : l) { b[i] += sign; if (b[i] == 0) b.erase(i); }
}
template<class Feature> Bag active(Color c, const Position& p) {
    typename Feature::IndexList list;
    Feature::append_active_indices(c, p, list);
    return bag(list);
}
Bag psq(Color c, const Position& p) {
    Bag result;
    for (Square s = SQ_A1; s <= SQ_H8; ++s)
        if (p.piece_on(s) != NO_PIECE)
            ++result[K32Q2::make_index(c, s, p.piece_on(s), p.square<KING>(c),
                                     bool(p.pieces(~c, QUEEN)))];
    return result;
}
template<class Feature, class Diff>
bool check(const Position& p, const Diff& diff, const Bag before[2],
           const Square oldKings[2], const std::string& beforeFen) {
    typename Feature::IndexList br[2], ba[2];
    Feature::append_changed_indices_both(p.square<KING>(WHITE), p.square<KING>(BLACK), diff,
                                         br[0], ba[0], br[1], ba[1]);
    for (Color c : {WHITE, BLACK}) {
        typename Feature::IndexList r, a;
        Feature::append_changed_indices(c, p.square<KING>(c), diff, r, a);
        if (bag(br[c]) != bag(r) || bag(ba[c]) != bag(a)) {
            std::cerr << "single/both mismatch feature=" << Feature::HashValue
                      << " color=" << c << "\n" << beforeFen << "\n" << p.fen() << "\n";
            return false;
        }
        if (FullThreats::OrientTBL[oldKings[c]] != FullThreats::OrientTBL[p.square<KING>(c)])
            continue;
        Bag expected = before[c];
        adjust(expected, r, -1); adjust(expected, a, +1);
        const auto actual = active<Feature>(c, p);
        if (expected != actual) {
            std::cerr << "active/incremental mismatch feature=" << Feature::HashValue
                      << " color=" << c << "\n" << beforeFen << "\n" << p.fen() << "\n";
            for (auto [i, n] : actual) expected[i] -= n;
            for (auto [i, n] : expected) if (n) std::cerr << i << ":" << n << " ";
            std::cerr << "\n";
            return false;
        }
    }
    return true;
}

int main(int argc, char** argv) {
    if (argc < 3) return 2;
    Attacks::init(); Position::init();
    std::ifstream input(argv[1]);
    std::vector<std::string> fens;
    for (std::string s; std::getline(input, s);) if (!s.empty()) fens.push_back(s);
    if (fens.empty()) return 2;
    const unsigned games = unsigned(std::stoul(argv[2]));
    const uint64_t seed = argc > 3 ? std::stoull(argv[3]) : 20261020;
    std::mt19937_64 rng(seed);
    uint64_t moves = 0, captures = 0, castles = 0, eps = 0, promotions = 0, undos = 0;
    unsigned maxDirty = 0;
    for (unsigned game = 0; game < games; ++game) {
        Position p;
        std::array<StateInfo, 512> states;
        std::vector<Move> history;
        const auto error = p.set(fens[game % fens.size()], true, &states[0]);
        if (error) { std::cerr << error->what() << "\n"; return 2; }
        for (unsigned iteration = 0; iteration < 250 && history.size() < 500; ++iteration) {
            MoveList<ALL> legal(p);
            if (!legal.size()) break;
            const auto m = *(legal.begin() + rng() % legal.size());
            const std::string beforeFen = p.fen();
            const Square kings[2] = {p.square<KING>(WHITE), p.square<KING>(BLACK)};
            Bag threats[2], pairs[2], squares[2];
            for (Color c : {WHITE, BLACK}) {
                threats[c] = active<FullThreats>(c, p);
                pairs[c] = active<PP_3Wide>(c, p);
                squares[c] = psq(c, p);
            }
            captures += p.capture(m);
            castles += m.type_of() == CASTLING;
            eps += m.type_of() == EN_PASSANT;
            promotions += m.type_of() == PROMOTION;
            Dirties d{};
            p.do_move(m, states[history.size() + 1], p.gives_check(m), d, nullptr, nullptr);
            history.push_back(m);
            ++moves;
            maxDirty = std::max(maxDirty, unsigned(d.dirtyThreats.list.size()));
            if (!check<FullThreats>(p, d.dirtyThreats, threats, kings, beforeFen)
                || !check<PP_3Wide>(p, d.dirtyPawnPairs, pairs, kings, beforeFen)) return 1;
            for (Color c : {WHITE, BLACK}) if (!K32Q2::requires_refresh(d.dirtyPiece, c)) {
                K32Q2::IndexList r, a;
                K32Q2::append_changed_indices(c, p.square<KING>(c), d.dirtyPiece,
                                              bool(p.pieces(~c, QUEEN)), r, a);
                adjust(squares[c], r, -1); adjust(squares[c], a, +1);
                if (squares[c] != psq(c, p)) {
                    std::cerr << "PSQ mismatch\n" << beforeFen << "\n" << p.fen() << "\n";
                    return 1;
                }
            }
            if (history.size() > 6 && rng() % 13 == 0) {
                const unsigned n = 1 + unsigned(rng() % 4);
                for (unsigned i = 0; i < n; ++i) {
                    p.undo_move(history.back()); history.pop_back(); ++undos;
                }
            }
        }
        if ((game + 1) % 100 == 0)
            std::cout << "progress games=" << game+1 << " moves=" << moves << std::endl;
    }
    std::cout << "PASS seed=" << seed << " games=" << games << " moves=" << moves
              << " captures=" << captures << " castles=" << castles << " ep=" << eps
              << " promotions=" << promotions << " undos=" << undos
              << " max_dirty=" << maxDirty << std::endl;
}
