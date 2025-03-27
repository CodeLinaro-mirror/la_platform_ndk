#include <android/versioning.h>

// Create an unavailable symbol that's set to an availability version
// higher than any ABI's minimum SDK version.
extern "C" void AFoo() __INTRODUCED_IN(100);

int main(int, char**) {
  AFoo();
  return 0;
}
