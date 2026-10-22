#include <thread>
#include <utility>
struct owner { void run() {} };
int main() { owner value; std::thread first(&owner::run, &value); std::thread second(std::move(first)); second.join(); }
