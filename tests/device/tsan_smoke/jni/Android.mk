LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := tsan_smoke
LOCAL_CPP_EXTENSION := .cc
LOCAL_SRC_FILES := tsan_tiny_race_test.cc
LOCAL_CFLAGS := -fsanitize=thread
LOCAL_LDFLAGS := -fsanitize=thread
LOCAL_STATIC_LIBRARIES := googletest_main
include $(BUILD_EXECUTABLE)

$(call import-module,third_party/googletest)
