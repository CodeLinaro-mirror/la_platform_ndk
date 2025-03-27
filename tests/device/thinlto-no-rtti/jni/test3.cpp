// A linkonce_odr typeinfo variable for Foo will be output into this LLVM IR output file.

#include <stdio.h>

#include "test.h"

int main() {
  try {
    throw_foo();
  } catch (Foo) {
    return 0;
  } catch (...) {
    fprintf(stderr, "error: uncaught exception\n");
    return 1;
  }
  fprintf(stderr, "error: no exception\n");
  return 1;
}
