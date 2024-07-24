# Changelog

Report issues to [GitHub].

For Android Studio issues, go to https://b.android.com and file a bug using the
Android Studio component, not the NDK component.

If you're a build system maintainer that needs to use the tools in the NDK
directly, see the [build system maintainers guide].

[GitHub]: https://github.com/android/ndk/issues
[build system maintainers guide]:
  https://android.googlesource.com/platform/ndk/+/master/docs/BuildSystemMaintainers.md

## Announcements

## Changes

- Updated LLVM to clang-r530567. See `clang_source_info.md` in the toolchain
  directory for version information.
- `PAGE_SIZE` is no longer defined by default for arm64-v8a or x86_64. To
  re-enable, set `APP_SUPPORT_FLEXIBLE_PAGE_SIZES` (ndk-build) or
  `ANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES` (CMake) to false. See [Support 16 KB
  page sizes] for more information.
- The default alignment of shared libraries for arm64-v86 and x86_64 is now 16k.
  To revert to 4k alignment, set `APP_SUPPORT_FLEXIBLE_PAGE_SIZES` (ndk-build)
  or `ANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES` (CMake) to false. See [Support 16 KB
  page sizes] for more information.

  Known issue: x86_64 is still 4k aligned by default. That will be fixed before
  final release.

[Support 16 KB page sizes]:
  https://developer.android.com/guide/practices/page-sizes
