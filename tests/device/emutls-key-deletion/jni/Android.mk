LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := direct_main
LOCAL_SRC_FILES := test_core.cpp direct_main.cpp
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := ndktest
LOCAL_SRC_FILES := test_core.cpp
include $(BUILD_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := dlclose_main
LOCAL_SRC_FILES := dlclose_main.cpp
include $(BUILD_EXECUTABLE)
