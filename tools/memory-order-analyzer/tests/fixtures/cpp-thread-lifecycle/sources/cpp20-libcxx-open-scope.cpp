#include <thread>
void external_worker();
void launch() { std::thread thread(external_worker); thread.detach(); }
