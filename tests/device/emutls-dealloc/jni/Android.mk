LOCAL_PATH := $(call my-dir)

# Turn on ASAN to help detect use-after-free. The test is still useful without
# ASAN. (Avoid ASAN on x86 to work around http://b/37130178.)
ASAN_FLAG :=
ifneq ($(filter $(TARGET_ARCH_ABI),armeabi-v7a arm64-v8a),)
    ASAN_FLAG := -fsanitize=address
endif

include $(CLEAR_VARS)
LOCAL_MODULE := pthread_test
LOCAL_SRC_FILES := pthread_test.cpp
LOCAL_STATIC_LIBRARIES := googletest_main
LOCAL_CFLAGS := $(ASAN_FLAG)
LOCAL_LDFLAGS := $(ASAN_FLAG)
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := tls_var
LOCAL_SRC_FILES := tls_var.cpp
LOCAL_STATIC_LIBRARIES := googletest_main
LOCAL_CFLAGS := $(ASAN_FLAG)
LOCAL_LDFLAGS := $(ASAN_FLAG)
include $(BUILD_EXECUTABLE)

$(call import-module,third_party/googletest)
