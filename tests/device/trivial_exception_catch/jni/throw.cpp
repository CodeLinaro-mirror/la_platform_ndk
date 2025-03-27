// Regression test for https://github.com/android/ndk/issues/1769.
#include <stdexcept>
#include <string>
#include <iostream>

void f() {
  std::string s = "test";
  std::cout << s << std::endl;
  throw std::runtime_error("Test");
}


int main() {
  try {
    f();
  } catch(const std::exception&) {
  }
}
