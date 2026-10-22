#include <thread>
struct Item { int payload{}; } first, second;
int main() { std::jthread thread([] { first.payload = 1; }); return second.payload; }
