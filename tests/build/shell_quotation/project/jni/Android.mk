LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := foo
LOCAL_SRC_FILES := foo.cpp
LOCAL_SHORT_COMMANDS := false
include $(BUILD_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := foo_short_local
LOCAL_SRC_FILES := foo.cpp
LOCAL_SHORT_COMMANDS := true
include $(BUILD_SHARED_LIBRARY)
