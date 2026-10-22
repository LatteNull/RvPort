#include <thread>
static void worker(int *value) { ++*value; }
int main() { int value = 0; std::thread thread(worker, &value); thread.join(); return value != 1; }
