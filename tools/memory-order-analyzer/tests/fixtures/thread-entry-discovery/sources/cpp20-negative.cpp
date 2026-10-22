#include <thread>
namespace boost { struct thread { template<class F> explicit thread(F) {} }; }
struct Form { template<class F> void submit(F) {} };
static void worker() {}
static std::thread factory() { return std::thread(worker); }
int main() {
  std::thread idle;
  std::thread active(worker);
  std::thread moved(std::move(active));
  std::thread returned = factory();
  boost::thread unsupported(worker);
  Form form;
  form.submit(worker);
  moved.join();
  returned.join();
}
