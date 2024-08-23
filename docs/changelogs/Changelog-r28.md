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
  - Runtime libraries for non-Android have been removed reduce disk usage.
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
- [Issue 2058]: [Weak API references] now work for libc APIs. This was enabled
  by removing the explicit `#if __ANDROID_API__ >= ...` guards that previously
  wrapped declarations in libc headers.

  If your project contains polyfills for any of those APIs, this change may
  break your build due to the conflicting declarations. The simplest fix is to
  rename your polyfill to not collide with libc. For example, rename
  `conflicting_api` to `conflicting_api_fallback` and call that instead. Use
  `#define conflicting_api() conflicting_api_fallback()` if you want to avoid
  rewriting callsites.

  Please open a bug if you run into issues with existing polyfills. We may be
  able to add the polyfill directly to the NDK.

[Issue 2058]: https://github.com/android/ndk/issues/2058
[Weak API references]: http://go/android-dev/ndk/guides/using-newer-apis

[Support 16 KB page sizes]:
  https://developer.android.com/guide/practices/page-sizes
