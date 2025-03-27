#include <stdio.h>

extern "C" void test_func();

int main() {
  test_func();
  return 0;
}
