#include <thread>
void launch() { std::thread thread([] {}); thread.join(); }
