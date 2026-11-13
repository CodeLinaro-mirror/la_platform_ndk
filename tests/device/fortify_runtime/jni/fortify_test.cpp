#include <memory.h>

#include <android/api-level.h>

#include "gtest/gtest.h"
#include "gtest/gtest-death-test.h"

static const char* expected_stderr() {
  if (android_get_device_api_level() <= 23) {
    // Prior to API 24, Bionic's FORTIFY diagnostics did not include sizes.
    return "memset: prevented write past end of buffer";
  } else {
    return "memset: prevented 5-byte write into 4-byte buffer";
  }
}

TEST(fortify, smoke) {
  char cs[4];
  char* p = cs;
  ASSERT_DEATH(memset(p, 0, 5), expected_stderr());
}
