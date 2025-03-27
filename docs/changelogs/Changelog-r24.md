# Changelog

Report issues to [GitHub].

For Android Studio issues, follow the docs on the [Android Studio site].

If you're a build system maintainer that needs to use the tools in the NDK
directly, see the [build system maintainers guide].

[GitHub]: https://github.com/android/ndk/issues
[Android Studio site]: http://tools.android.com/filing-bugs
[build system maintainers]: https://android.googlesource.com/platform/ndk/+/master/docs/BuildSystemMaintainers.md

## Announcements

* The GNU Assembler (GAS), has been removed. If you were building with
  `-fno-integrated-as` you'll need to remove that flag. See
  [Clang Migration Notes] for advice on making assembly compatible with LLVM.

* GDB has been removed. Use LLDB instead. Note that `ndk-gdb` uses LLDB by
  default, and Android Studio has only ever supported LLDB.

* Jelly Bean (APIs 16, 17, and 18) is no longer supported. The minimum OS
  supported by the NDK is KitKat (API level 19).

* Non-Neon devices are no longer supported. A very small number of very old
  devices do not support Neon so most apps will not notice aside from the
  performance improvement.

* RenderScript build support has been removed. RenderScript was
  [deprecated](https://developer.android.com/about/versions/12/deprecations#renderscript)
  in Android 12. If you have not finished migrating your apps away from
  RenderScript, NDK r23 LTS can be used.

[Clang Migration Notes]: https://android.googlesource.com/platform/ndk/+/master/docs/ClangMigration.md

## r24b

* [Issue 1693]: The NDK's toolchain file for CMake (`android.toolchain.cmake`)
  defaults to the legacy toolchain file for all versions of CMake. The new
  toolchain file can still be enabled using
  `-DANDROID_USE_LEGACY_TOOLCHAIN_FILE=OFF`.

[Issue 1693]: https://github.com/android/ndk/issues/1693

## Changes

* Includes Android 12L APIs.
* Updated LLVM to clang-r437112b, based on LLVM 14 development.
  * [Issue 1590]: Fix LLDB help crash.
* [Issue 1108]: Removed `mbstowcs` and `wcstombs` from the pre-API 21 stubs and
  moved the implementation to `libandroid_support` to fix those APIs on old
  devices.
* [Issue 1299]: Additional Apple M1 support:
  * [Issue 1410]: Fixed incorrect host tool directory identification in
    ndk-build on M1 macs.
  * [Issue 1544]: LLVM tools are now universal binaries.
  * [Issue 1546]: Make is now a universal binary.
* [Issue 1479]: Added `LOCAL_BRANCH_PROTECTION` option to ndk-build for using
  `-mbranch-protection` with aarch64 without breaking other ABIs. Example use:
  `LOCAL_BRANCH_PROTECTION := standard`.
* [Issue 1492]: Windows Make now works with `-O`, and ndk-build now uses it by
  default.
* [Issue 1559]: Added `LOCAL_ALLOW_MISSING_PREBUILT` option to
  `PREBUILT_SHARED_LIBRARY` and `PREBUILT_STATIC_LIBRARY` which defers failures
  for missing prebuilts to build time. This enables use cases within AGP where
  one module provides "pre" built libraries to another module.
* [Issue 1587]: ndk-stack is now tolerant of unsorted zip infos.
* [Issue 1589]: Fixed broken stack traces on API 29 devices when using a
  minSdkVersion of 29.
* [Issue 1593]: Improved ndk-which to fall back to LLVM tools when the GNU names
  are used. For example, `ndk-which strip` will now return the path to
  `llvm-strip` instead of nothing.
* [Issue 1610]: Fixed handling of `ANDROID_NATIVE_API_LEVEL` in the new CMake
  toolchain file.
* [Issue 1618]: Corrected `CMAKE_ANDROID_EXCEPTIONS` behavior for the new CMake
  toolchain file.
* [Issue 1623]: Fixed behavior of the legacy CMake toolchain file when used with
  new versions of CMake (incompatible `-gcc-toolchain` argument).
* [Issue 1656]: The new CMake toolchain file now ignores `ANDROID_ARM_MODE` when
  it is passed for ABIs other than armeabi-v7a like the legacy toolchain file
  did. With CMake 3.22 it is an error to set `CMAKE_ANDROID_ARM_MODE` for other
  ABIs, so this fixes a potential incompatibility between the legacy and new
  toolchains when using CMake 3.22+.
* Removed `make-standalone-toolchain.sh`. This was broken in a previous release
  and it was unnoticed, so it seems unused. `make_standalone_toolchain.py`
  remains, but neither has been needed since NDK r19 since the toolchain can be
  invoked directly.

[Issue 1108]: https://github.com/android/ndk/issues/1108
[Issue 1299]: https://github.com/android/ndk/issues/1299
[Issue 1410]: https://github.com/android/ndk/issues/1410
[Issue 1479]: https://github.com/android/ndk/issues/1479
[Issue 1492]: https://github.com/android/ndk/issues/1492
[Issue 1544]: https://github.com/android/ndk/issues/1544
[Issue 1546]: https://github.com/android/ndk/issues/1546
[Issue 1559]: https://github.com/android/ndk/issues/1559
[Issue 1587]: https://github.com/android/ndk/issues/1587
[Issue 1589]: https://github.com/android/ndk/issues/1589
[Issue 1590]: https://github.com/android/ndk/issues/1590
[Issue 1593]: https://github.com/android/ndk/issues/1593
[Issue 1610]: https://github.com/android/ndk/issues/1610
[Issue 1618]: https://github.com/android/ndk/issues/1618
[Issue 1623]: https://github.com/android/ndk/issues/1623
[Issue 1656]: https://github.com/android/ndk/issues/1656

## Known Issues

This is not intended to be a comprehensive list of all outstanding bugs.

* [Issue 360]: `thread_local` variables with non-trivial destructors will cause
  segfaults if the containing library is `dlclose`ed. This was fixed in API 28,
  but code running on devices older than API 28 will need a workaround. The
  simplest fix is to **stop calling `dlclose`**. If you absolutely must continue
  calling `dlclose`, see the following table:

  |                   | Pre-API 23           |  APIs 23-27   | API 28+ |
  | ----------------- | -------------------- | ------------- | ------- |
  | No workarounds    | Works for static STL | Broken        | Works   |
  | `-Wl,-z,nodelete` | Works for static STL | Works         | Works   |
  | No `dlclose`      | Works                | Works         | Works   |

  If your code must run on devices older than M (API 23) and you cannot use the
  static STL (common), **the only fix is to not call `dlclose`**, or to stop
  using `thread_local` variables with non-trivial destructors.

  If your code does not need to run on devices older than API 23 you can link
  with `-Wl,-z,nodelete`, which instructs the linker to ignore `dlclose` for
  that library. You can backport this behavior by not calling `dlclose`.

  The fix in API 28 is the standardized inhibition of `dlclose`, so you can
  backport the fix to older versions by not calling `dlclose`.

* [Issue 988]: Exception handling when using ASan via wrap.sh can crash. To
  workaround this issue when using libc++_shared, ensure that your application's
  libc++_shared.so is in `LD_PRELOAD` in your `wrap.sh` as in the following
  example:

  ```bash
  #!/system/bin/sh
  HERE="$(cd "$(dirname "$0")" && pwd)"
  export ASAN_OPTIONS=log_to_syslog=false,allow_user_segv_handler=1
  ASAN_LIB=$(ls $HERE/libclang_rt.asan-*-android.so)
  if [ -f "$HERE/libc++_shared.so" ]; then
      # Workaround for https://github.com/android/ndk/issues/988.
      export LD_PRELOAD="$ASAN_LIB $HERE/libc++_shared.so"
  else
      export LD_PRELOAD="$ASAN_LIB"
  fi
  "$@"
   ```

  There is no known workaround for libc++_static.

  Note that because this is a platform bug rather than an NDK bug this cannot be
  fixed with an NDK update. This workaround will be necessary for code running
  on devices that do not contain the fix, and the bug has not been fixed even in
  the latest release of Android.

[Issue 360]: https://github.com/android/ndk/issues/360
[Issue 988]: https://github.com/android/ndk/issues/988
