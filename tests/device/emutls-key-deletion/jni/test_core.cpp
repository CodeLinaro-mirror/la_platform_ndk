#include <stdio.h>
#include <stdlib.h>

// Regression test for b/80453944. Verify that the __thread variable is still
// usable in (a) destructor functions of ordinary priority and (b) C++
// destructors for static objects.

__thread int tlsvar1;
__thread int tlsvar2 = 20;
int expected1;
int expected2 = 20;

static void dump_vars(const char* title) {
  tlsvar1++;
  tlsvar2++;
  expected1++;
  expected2++;

  if (tlsvar1 != expected1) {
    fprintf(stderr, "%s: %d != %d\n", title, tlsvar1, expected1);
    abort();
  }
  if (tlsvar2 != expected2) {
    fprintf(stderr, "%s: %d != %d\n", title, tlsvar2, expected2);
    abort();
  }
}

struct CxxDtor {
  ~CxxDtor() { dump_vars("~A()"); }
};

static CxxDtor cxx_dtor;

__attribute__((destructor)) void dtorfn() { dump_vars("dtorfn"); }

extern "C" void test_func() {
  atexit([] { dump_vars("atexit1"); });
  atexit([] { dump_vars("atexit2"); });

  tlsvar1 = 10;
  expected1 = 10;
}
