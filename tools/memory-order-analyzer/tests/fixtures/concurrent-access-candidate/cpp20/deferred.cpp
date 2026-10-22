#include <future>
int shared_value;
int main() { auto future = std::async(std::launch::deferred, [] { shared_value = 1; }); int value = shared_value; future.get(); return value; }
