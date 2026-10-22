#include <mutex>

int payload;
std::mutex mutex;
void write_payload() { std::unique_lock<std::mutex> owner(mutex, std::defer_lock); owner.lock(); payload = 1; }
int read_payload() { std::unique_lock<std::mutex> owner(mutex); int value = payload; owner.unlock(); return value; }
