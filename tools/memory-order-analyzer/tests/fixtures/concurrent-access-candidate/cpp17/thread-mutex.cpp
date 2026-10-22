#include <mutex>
#include <thread>

struct State { int payload{}; std::mutex mutex; } state;
void writer() { std::lock_guard<std::mutex> lock(state.mutex); state.payload = 1; }
int main() { std::thread thread(writer); std::lock_guard<std::mutex> lock(state.mutex); int value = state.payload; thread.join(); return value; }
