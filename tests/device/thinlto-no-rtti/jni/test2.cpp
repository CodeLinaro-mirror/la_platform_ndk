// A linkonce_odr typeinfo variable for Foo will be output into this LLVM IR output file.

#include "test.h"

void throw_foo() {
  throw Foo();
}
