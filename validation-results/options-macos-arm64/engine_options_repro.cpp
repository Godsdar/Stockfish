#include <iostream>
#include <sstream>
#include "attacks.h"
#include "bitboard.h"
#include "engine.h"
#include "position.h"

int main() {
    Stockfish::Attacks::init();
    Stockfish::Position::init();
    Stockfish::Engine first;
    Stockfish::Engine second;
    std::ostringstream a,b;
    a << first.get_options(); b << second.get_options();
    std::cout << "FIRST" << a.str() << "\nSECOND" << b.str() << '\n';
    std::cout << "equal=" << (a.str()==b.str()) << '\n';
    return a.str()==b.str()?0:1;
}
