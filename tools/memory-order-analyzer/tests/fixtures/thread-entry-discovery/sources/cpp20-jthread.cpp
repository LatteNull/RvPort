#include <thread>
static void plain() {}
int main() {
  std::jthread first(plain);
  std::jthread second([](std::stop_token) {});
}
