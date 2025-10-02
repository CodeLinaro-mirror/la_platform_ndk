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

## Changes

- Updated LLVM to clang-r574158. See `clang_source_info.md` in the toolchain
  directory for version information.
  - [Issue 2073]: Fixed runtime segfault when using LTO and nested exception
    handlers.
  - [Issue 2160]: Fix Clang crash on invalid code.

[Issue 2073]: https://github.com/android/ndk/issues/2073
[Issue 2160]: https://github.com/android/ndk/issues/2160
