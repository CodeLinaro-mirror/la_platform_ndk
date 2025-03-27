#include <stdint.h>
#include <stdlib.h>

void bad_api(const uint8_t*, size_t) {
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  bad_api(data, size);
  return 0;
}
