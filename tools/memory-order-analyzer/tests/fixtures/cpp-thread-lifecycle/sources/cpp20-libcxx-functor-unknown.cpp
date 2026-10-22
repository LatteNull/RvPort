#include <thread>
struct overloaded { void operator()() {} void operator()(int) {} };
void launch() { std::thread thread(overloaded{}); thread.join(); }
