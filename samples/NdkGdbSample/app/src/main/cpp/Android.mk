LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := libapp
LOCAL_SRC_FILES := app.cpp
include $(BUILD_SHARED_LIBRARY)
