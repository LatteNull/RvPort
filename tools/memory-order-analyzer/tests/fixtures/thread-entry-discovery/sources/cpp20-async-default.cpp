#include <future>
static void worker() {}
int main() {
  auto implementation_choice = std::async(worker);
  auto combined = std::async(std::launch::async | std::launch::deferred, worker);
  implementation_choice.get();
  combined.get();
}
