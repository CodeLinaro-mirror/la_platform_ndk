LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := fuzz_test
LOCAL_SRC_FILES := fuzz_test.cpp
LOCAL_CPPFLAGS := -fsanitize=fuzzer
LOCAL_LDFLAGS := -fsanitize=fuzzer
include $(BUILD_EXECUTABLE)

# We need to pass some arguments to the fuzz test, but we don't control its main
# and the test runner doesn't have infrastructure for that, so we mark the fuzz
# test itself as run_unsupported to stop it from being run and instead launch it
# with this.
include $(CLEAR_VARS)
LOCAL_MODULE := fuzz_test_wrapper
LOCAL_SRC_FILES := fuzz_test_wrapper.cpp
include $(BUILD_EXECUTABLE)
