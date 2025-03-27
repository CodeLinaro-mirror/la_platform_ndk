#include <gtest/gtest.h>
#include <android/trace.h>
#include <android/api-level.h>

TEST(weak_symbols, crash_if_call_unavailable) {
   if (android_get_device_api_level() >= 29) {
     GTEST_SKIP() << "Test only valid for post-API 29 devices";
   }
   // 4770 is a cookie example from
   // http://cs/android/cts/hostsidetests/atrace/AtraceTestApp/jni/CtsTrace.cpp;l=30;rcl=214cc4d8356fdb1ba4a63ae5baf86c6d76074233
   ASSERT_DEATH(ATrace_beginAsyncSection("ndk::asyncBeginEndSection", 4770), "");
}

TEST(weak_symbols, pass_if_call_available) {
   if (android_get_device_api_level() < 29) {
     GTEST_SKIP() << "Test not valid for pre-API 29 devices";
   }
   // 4770 is a cookie example from
   // http://cs/android/cts/hostsidetests/atrace/AtraceTestApp/jni/CtsTrace.cpp;l=30;rcl=214cc4d8356fdb1ba4a63ae5baf86c6d76074233
   ATrace_beginAsyncSection("ndk::asyncBeginEndSection", 4770);
}


