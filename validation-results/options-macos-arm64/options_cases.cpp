#include <iostream>
#include <sstream>
#include <string>
#include "ucioption.h"

namespace Stockfish {
std::ostream& operator<<(std::ostream& os, SyncCout) { return os; }
}
using namespace Stockfish;

static std::string text(const OptionsMap& m) {
    std::ostringstream out;
    out << m;
    return out.str();
}
static std::string spin(const std::string& name) {
    return "\noption name " + name + " type spin default 2 min 1 max 8";
}
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    std::string scenario=argv[1];
    bool pass=false;
    if (scenario == "empty") {
        OptionsMap a; pass=text(a).empty();
    } else if (scenario == "callback") {
        OptionsMap a,b; int observed=0, calls=0;
        a.add("Unrelated", Option(2, 1, 8));
        b.add("Hash", Option(2,1,8,[&](const Option& value) { observed=int(value); ++calls; return std::nullopt; }));
        std::istringstream valid("name hAsH value 7"); b.setoption(valid);
        std::istringstream invalid("name Hash value 9"); b.setoption(invalid);
        pass=int(b["hash"])==7 && observed==7 && calls==1 && text(b)==spin("Hash");
    } else if (scenario == "single") {
        OptionsMap a;
        a.add("Zulu", Option(2, 1, 8)); a.add("Alpha", Option(2, 1, 8));
        pass=text(a)==spin("Zulu")+spin("Alpha");
    } else if (scenario == "sequential") {
        OptionsMap a,b;
        a.add("A", Option(2, 1, 8)); b.add("B", Option(2, 1, 8));
        pass=text(a)==spin("A") && text(b)==spin("B");
    } else if (scenario == "interleaved") {
        OptionsMap a,b;
        a.add("A", Option(2, 1, 8)); b.add("B", Option(2, 1, 8));
        a.add("C", Option(2, 1, 8)); b.add("D", Option(2, 1, 8));
        pass=text(a)==spin("A")+spin("C") && text(b)==spin("B")+spin("D");
    } else if (scenario == "lifetime") {
        { OptionsMap temporary; temporary.add("Old", Option(2, 1, 8)); }
        OptionsMap a; a.add("New", Option(2, 1, 8));
        pass=text(a)==spin("New");
    } else if (scenario == "combo") {
        OptionsMap a;
        a.add("Style", Option("alpha var beta", "alpha"));
        std::istringstream command("name Style value beta"); a.setoption(command);
        a.add("Hash", Option(2, 1, 8));
        pass=a["Style"]=="beta" && text(a)=="\noption name Style type combo default alpha var beta"+spin("Hash");
    } else if (scenario == "duplicate") {
        OptionsMap a; a.add("Hash", Option(2, 1, 8));a.add("HASH", Option(2, 1, 8));
        return 3; // Must terminate on duplicate, as before.
    } else return 2;
    std::cout << scenario << ": " << (pass?"PASS":"FAIL") << '\n';
    return pass?0:1;
}
