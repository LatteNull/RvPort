#include <thread>
static void worker() {}
int main() { std::thread thread(worker); thread.join(); }
