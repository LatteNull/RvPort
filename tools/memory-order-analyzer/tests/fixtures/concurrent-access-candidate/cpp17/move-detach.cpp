#include <thread>
int shared_value;
void writer() { shared_value = 1; }
int main() { std::thread first(writer); std::thread second = std::move(first); second.detach(); return shared_value; }
