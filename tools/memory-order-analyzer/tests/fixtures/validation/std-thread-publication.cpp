// Independent experimental fixture, not copied from either archived checker.
// CASE: 0 plain, 1 relaxed, 2 release/acquire, 3 default seq_cst,
//       4 fences, 5 late acquire, 6 renamed relaxed flag, 7 all-atomic relaxed.
#include <atomic>
#include <thread>

#ifndef CASE
#define CASE 2
#endif

#if CASE == 7
std::atomic<int> payload{0};
#else
int payload = 0;
#endif

#if CASE == 0
bool ready = false;
#elif CASE == 6
std::atomic<bool> signal{false};
#define ready signal
#else
std::atomic<bool> ready{false};
#endif

int observed = 0;

void producer() {
#if CASE == 7
    payload.store(42, std::memory_order_relaxed);
#else
    payload = 42;
#endif
#if CASE == 0
    ready = true;
#elif CASE == 2 || CASE == 5
    ready.store(true, std::memory_order_release);
#elif CASE == 3
    ready.store(true);
#elif CASE == 4
    std::atomic_thread_fence(std::memory_order_release);
    ready.store(true, std::memory_order_relaxed);
#else
    ready.store(true, std::memory_order_relaxed);
#endif
}

void consumer() {
#if CASE == 0
    while (!ready) {}
#elif CASE == 2
    while (!ready.load(std::memory_order_acquire)) {}
#elif CASE == 3
    while (!ready.load()) {}
#else
    while (!ready.load(std::memory_order_relaxed)) {}
#endif
#if CASE == 4
    std::atomic_thread_fence(std::memory_order_acquire);
#endif
#if CASE == 7
    observed = payload.load(std::memory_order_relaxed);
#else
    observed = payload;
#endif
#if CASE == 5
    (void)ready.load(std::memory_order_acquire); // Too late to protect payload.
#endif
}

int main() {
    std::thread writer(producer);
    std::thread reader(consumer);
    writer.join();
    reader.join();
    return observed == 42 ? 0 : 1;
}
