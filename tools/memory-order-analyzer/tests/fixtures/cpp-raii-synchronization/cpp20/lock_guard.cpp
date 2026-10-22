#include <mutex>

int payload;
std::mutex mutex;
void write_payload() { std::lock_guard<std::mutex> guard(mutex); payload = 1; }
int read_payload() { std::lock_guard<std::mutex> guard(mutex); return payload; }
