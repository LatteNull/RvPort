#include <thread>
int shared_value;
int main() { std::thread thread([] { shared_value = 1; }); int value = shared_value; thread.join(); return value; }
