LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := weak_symbols
LOCAL_SRC_FILES := weak_symbols.cpp
LOCAL_STATIC_LIBRARIES := googletest_main
LOCAL_LDLIBS := -landroid
include $(BUILD_EXECUTABLE)

$(call import-module,third_party/googletest)