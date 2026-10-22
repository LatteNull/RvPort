#include <future>
#include <thread>
struct Owner { void member() {} };
struct Functor { void operator()() const {} };
int main() {
  Owner owner;
  std::thread lambda([] {});
  std::thread member(&Owner::member, &owner);
  std::thread functor(Functor{});
  auto asynchronous = std::async(std::launch::async, &Owner::member, &owner);
  lambda.join(); member.join(); functor.join(); asynchronous.get();
}
