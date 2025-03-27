#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <string>

#include <gtest/gtest.h>

#if !defined(__aarch64__)
#error "HWASan is only supported on AArch64."
#endif

#if !__has_feature(hwaddress_sanitizer)
#error "Want HWASan build"
#endif


TEST(HWAddressSanitizer, OOB) {
  EXPECT_DEATH({
      volatile char* x = const_cast<volatile char*>(reinterpret_cast<char*>(malloc(1)));
      x[1] = '2';
      }, ".*HWAddressSanitizer.*");
}
