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

- Updated LLVM to clang-r547379. See `clang_source_info.md` in the toolchain
  directory for version information.
- ndk-stack will now find symbols in files with matching build IDs even if the
  file names do not match.
- ndk-stack will now find symbols in files with matching build IDs even if the
  name of the file is not present in the trace.
