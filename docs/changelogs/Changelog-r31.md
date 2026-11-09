# Changelog

Report issues to [GitHub].

For Android Studio issues, go to https://b.android.com and file a bug using the
Android Studio component, not the NDK component.

If you're a build system maintainer that needs to use the tools in the NDK
directly, see the [build system maintainers guide].

[GitHub]: https://github.com/android/ndk/issues
[build system maintainers guide]:
  https://android.googlesource.com/platform/ndk/+/mirror-goog-main-ndk/docs/BuildSystemMaintainers.md

## Announcements

- Lollipop (APIs 21 and 22) is no longer supported. The minimum OS supported by
  the NDK is Marshmallow (API level 23). See [Issue 2188] for details.

- NDK now supports Linux Arm64 as a host. We now provide both toolchains, sysroots,
  and other NDK tools all working on Linux Arm64. As a result of supporting Linux Arm64,
  we have dropped some NDK tools (shaderc and yasm). These are also mentioned in the Changes below.

- We have removed deprecated cpufeatures and ndk_helper libraries because they can be found in other
  places like [cpu_features] and teapot samples in [ndk-samples].

## Changes

- Updated LLVM to clang-r614150. See `clang_source_info.md` in the toolchain
  directory for version information.
  - [Issue 1261]: Enabled _LIBCPP_HAS_TRIVIAL_MUTEX_DESTRUCTION for Bionic.
  - [Issue 1914]: Enabled PAC/BTI for Android Targets by Default.
  - [Issue 2072]: Toolchain runtimes (excluding builtins and compiler-rt) are built with
    `FORTIFY_SOURCE=3` and stack-protector.
  - [Issue 2165]: Toolchain now supports libclang.lib for Windows.
  - [Issue 2101]: Fixed issue where optimizations appeared in Clang's vendor string which
    led to different host compilers to produce different binaries.
  - [Issue 2193]: Packed relocations for Android are now added automatically by Clang driver.
  - [Issue 2249]: Bundle llvm-profgen in the toolchain.
  - [Issue 2259]: Fixed linkage error when using std::jthread and C++20 modules.
- [Issue 1752]: Support Linux Arm64 as a host with more details available in the above
  announcement and in the issue.
- [Issue 2240]: Fixed stpncpy implementation to conform to the C standard when being used
  with FORTIFY_SOURCE.
- [Issue 2245]: ndk-build and the CMake toolchain file now enable
  `_FORTIFY_SOURCE=3` by default (upgraded from `_FORTIFY_SOURCE=2`).
- [Issue 2247]: Removed cpufeatures from the NDK. It has been deprecated for a
  long time. Use [cpu_features] instead, which has an `ndk_compat` library for
  code that still uses the old `cpu-features.h` API.
- [Issue 2251]: Removed ndk_helper from the NDK. It came from the teapot samples
  and is still available in [ndk-samples].
- [Issue 2252]: Removed shaderc from the NDK.
- [Issue 2253]: Removed yasm from the NDK.
- [Issue 2262]: Fixed wrong header file association for inlined C++ lambdas in simpleperf.
- [Issue 2263]: ndk-build and the CMake toolchain file now pass the same `--target` spelling
  as the NDK's clang wrapper scripts (for example, `aarch64-linux-android21` instead of
  `aarch64-none-linux-android21`). Clang requires the triple to match exactly when loading a
  PCH or module, so mixing them caused errors in tools like `clang-scan-deps`.

[Issue 1261]: https://github.com/android/ndk/issues/1261
[Issue 1752]: https://github.com/android/ndk/issues/1752
[Issue 1914]: https://github.com/android/ndk/issues/1914
[Issue 2072]: https://github.com/android/ndk/issues/2072
[Issue 2101]: https://github.com/android/ndk/issues/2101
[Issue 2165]: https://github.com/android/ndk/issues/2165
[Issue 2188]: https://github.com/android/ndk/issues/2188
[Issue 2193]: https://github.com/android/ndk/issues/2193
[Issue 2240]: https://github.com/android/ndk/issues/2240
[Issue 2245]: https://github.com/android/ndk/issues/2245
[Issue 2247]: https://github.com/android/ndk/issues/2247
[Issue 2249]: https://github.com/android/ndk/issues/2249
[Issue 2251]: https://github.com/android/ndk/issues/2251
[Issue 2252]: https://github.com/android/ndk/issues/2252
[Issue 2253]: https://github.com/android/ndk/issues/2253
[Issue 2259]: https://github.com/android/ndk/issues/2259
[Issue 2262]: https://github.com/android/ndk/issues/2262
[Issue 2263]: https://github.com/android/ndk/issues/2263
[cpu_features]: https://github.com/google/cpu_features
[ndk-samples]: https://github.com/android/ndk-samples/tree/main/teapots/common/ndk_helper
