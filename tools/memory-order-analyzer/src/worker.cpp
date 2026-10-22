#include "facts.h"
int main(int argc, const char *argv[]) {
  return moa::worker(argc, argv, llvm::outs(), llvm::errs());
}
