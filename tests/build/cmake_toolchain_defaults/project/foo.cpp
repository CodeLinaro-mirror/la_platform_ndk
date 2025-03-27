#if !defined(__ARM_ARCH_7A__)
#error ABI did not default to armeabi-v7a
#endif

// Update this whenever we raise the minimum API level in the NDK.
#if __ANDROID_API__ != 19
#error API level did not default to 19
#endif
