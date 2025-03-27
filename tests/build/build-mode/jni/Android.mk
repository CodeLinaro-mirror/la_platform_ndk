LOCAL_PATH := $(call my-dir)

ifneq ($(filter $(TARGET_ARCH_ABI), armeabi-v7a),)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_thumb2_neon
LOCAL_CFLAGS += -DCHECK_THUMB2 -DCHECK_NEON
LOCAL_SRC_FILES := main.c.neon
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_thumb2_neon_b
LOCAL_CFLAGS += -DCHECK_THUMB2 -DCHECK_NEON
LOCAL_SRC_FILES := main.c
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_thumb2_neon_c
LOCAL_CFLAGS += -DCHECK_THUMB2 -DCHECK_NEON
LOCAL_SRC_FILES := main.c
LOCAL_ARM_MODE := thumb
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_thumb2_neon_d
LOCAL_CFLAGS += -DCHECK_THUMB2 -DCHECK_NEON
LOCAL_SRC_FILES := main.c
LOCAL_ARM_NEON := true
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_armv7_neon
LOCAL_CFLAGS += -DCHECK_ARM -DCHECK_NEON
LOCAL_SRC_FILES := main.c.arm.neon
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_armv7_neon_b
LOCAL_CFLAGS += -DCHECK_ARM -DCHECK_NEON
LOCAL_SRC_FILES := main.c.arm
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_armv7_neon_c
LOCAL_CFLAGS += -DCHECK_ARM -DCHECK_NEON
LOCAL_SRC_FILES := main.c
LOCAL_ARM_MODE := arm
include $(BUILD_EXECUTABLE)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_armv7_neon_d
LOCAL_CFLAGS += -DCHECK_ARM -DCHECK_NEON
LOCAL_SRC_FILES := main.c
LOCAL_ARM_MODE := arm
LOCAL_ARM_NEON := true
include $(BUILD_EXECUTABLE)

endif # TARGET_ARCH_ABI == armeabi-v7a

# We only build a single binary for x86
#
ifeq ($(TARGET_ARCH),x86)

include $(CLEAR_VARS)
LOCAL_MODULE := test_build_mode_x86
LOCAL_CFLAGS += -DCHECK_X86
LOCAL_SRC_FILES := main.c
include $(BUILD_EXECUTABLE)

endif # TARGET_ARCH == x86
