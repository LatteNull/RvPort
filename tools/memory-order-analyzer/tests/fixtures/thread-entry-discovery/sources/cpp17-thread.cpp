#include <thread>
using worker_thread = std::thread;
static void worker() {}
int main() {
  worker_thread first(worker);
  std::thread second([] {});
  first.join();
  second.join();
}
