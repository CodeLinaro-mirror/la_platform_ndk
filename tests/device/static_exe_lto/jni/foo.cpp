#include <stdio.h>

static bool global_ctor_called = false;

struct SideEffectClass {
  SideEffectClass() {
    global_ctor_called = true;
  }
};

static SideEffectClass global{};

int main(int, char**) {
  // Regression test for https://github.com/android/ndk/issues/1461. Without the
  // fix, the global constructor will not have been called.
  if (!global_ctor_called) {
    fprintf(stderr, "Global constructor was not called before main\n");
    return 1;
  }
  return 0;
}