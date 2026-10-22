#include <mutex>
struct Guarded { std::mutex mutex; int payload; };
void update(Guarded *value) {
  std::lock_guard<std::mutex> lock(value->mutex);
  value->payload = 1;
}
