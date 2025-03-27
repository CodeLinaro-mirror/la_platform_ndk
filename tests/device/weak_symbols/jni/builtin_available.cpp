#include <gtest/gtest.h>
#include <android/trace.h>
#include <android/api-level.h>

TEST(weak_symbols, weak_symbol_enable) {
     bool called = false;
     if (__builtin_available(android 29, *)) {
       // 0 is an arbitrary cookie. The specific value doesn't matter because
       // this will never run concurrently.
       ATrace_beginAsyncSection("ndk::asyncBeginEndSection", 0);
       called = true;
     }
     ASSERT_EQ(android_get_device_api_level() >= 29, called);
}