LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := testlib
LOCAL_SRC_FILES := testlib.cpp
# Using a version script to ensure that the static libc++ is not re-exposed.
LOCAL_LDFLAGS := -Wl,--version-script,$(LOCAL_PATH)/libtestlib.map.txt
include $(BUILD_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := foo
LOCAL_SRC_FILES := foo.cpp
include $(BUILD_EXECUTABLE)
