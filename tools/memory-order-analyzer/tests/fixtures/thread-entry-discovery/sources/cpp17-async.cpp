#include <future>
static void worker() {}
int main() {
  auto asynchronous = std::async(std::launch::async, worker);
  auto deferred = std::async(std::launch::deferred, worker);
  asynchronous.get();
  deferred.get();
}
