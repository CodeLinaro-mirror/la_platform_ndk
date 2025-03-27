#include <iostream>

extern "C" void func() {
  try {
    throw 0;
  } catch (...) {
    std::cerr << "Caught" << std::endl;
  }
}
