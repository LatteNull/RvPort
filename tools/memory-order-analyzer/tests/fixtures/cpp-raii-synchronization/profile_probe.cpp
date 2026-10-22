#include <mutex>

std::mutex first;
std::mutex second;

void lock_guard_probe() {
  std::lock_guard<std::mutex> guard(first);
}

void unique_lock_probe() {
  std::unique_lock<std::mutex> guard(first, std::defer_lock);
  guard.lock();
  guard.unlock();
}

void scoped_lock_probe() {
  std::scoped_lock guard(first, second);
}
