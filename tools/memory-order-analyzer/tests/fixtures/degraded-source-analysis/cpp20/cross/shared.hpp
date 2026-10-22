#include <atomic>
struct shared_state { std::atomic<int> ready; int payload; };
extern shared_state state;
void publish();
void consume();
