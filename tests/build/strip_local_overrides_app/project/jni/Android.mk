LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := foo
LOCAL_SRC_FILES := foo.cpp
LOCAL_STRIP_MODE := --strip-unneeded
include $(BUILD_SHARED_LIBRARY)
