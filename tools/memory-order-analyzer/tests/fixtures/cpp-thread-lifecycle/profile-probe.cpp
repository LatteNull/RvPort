#include <thread>
#include <utility>

void worker(int *value) { ++*value; }

struct owner {
  int value = 0;
  void member() { ++value; }
};

struct functor {
  void operator()() const {}
};

void probe_join() {
  int value = 0;
  std::thread first(worker, &value);
  std::thread moved(std::move(first));
  if (moved.joinable()) moved.join();
}

void probe_detach() {
  owner value;
  std::thread member(&owner::member, &value);
  member.detach();
  std::thread lambda([] {});
  lambda.join();
  std::thread object(functor{});
  object.join();
}
