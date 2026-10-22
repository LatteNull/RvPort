#include <mutex>

int payload;
std::mutex first;
std::mutex second;
void write_payload() { std::scoped_lock guard(first, second); payload = 1; }
int read_payload() { std::scoped_lock guard(first, second); return payload; }
