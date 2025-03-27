# Architecture

The latest version of this document is available at
https://android.googlesource.com/platform/ndk/+/master/docs/Architecture.md.

The core NDK is the zip file that is built in this repository and distributed by
the SDK manager. It bundles the outputs of several other projects into a package
that is directly usable by app developers, and also includes a few projects
maintained directly in this repository.

More broadly, "the NDK" can refer to the C ABI exposed to apps by the OS (AKA
"the platform").

## Code map

The code in the NDK repo (the "repo" repository, the meta-repo that was created
with `repo init` and `repo sync`, the parent directory of this git repo) is
organized as follows:

### bionic

The source for bionic, Android's libc (and friends). The sources and includes
for building the CRT objects come from this repository.

### development

The repository itself is overly broad. We include it for the adb python package.

### external

Most third-party code lives in external. For example, this is where googletest
and some of the vulkan code lives.

### ndk

The main NDK repository. This is where the build systems and the NDK's own build
and test systems live. This directory is organized as:

#### Main directory

The main directory contains the entry points to the build (`checkbuild.py`) and
test (`run_tests.py`) scripts, as well as Python configuration files like
mypy.ini and pylintrc. The other loose files in this directory such as ndk-gdb
are the sources for tools that are shipped in the NDK that should probably be
moved into their own directory for clarity.

#### bootstrap

Python 2/3 library for bootstrapping our build and test tools with an up to date
Python 3.

#### build

Contains the build systems shipped in the NDK:

* CMake toolchain files
* ndk-build
* `make_standalone_toolchain.py`

#### docs

Documentation primarily for core NDK development. Some additional documentation
lives here as well but most user documentation lives in google3.

#### infra

Some infrastructure scripts like a Dockerfile that can be used to build the NDK.

#### meta

Metadata for the NDK intended for consumption by external tools and build
systems to avoid needing to hard code or infer properties like the minimum and
maximum OS versions or ABIs supported.

#### ndk

The Python package used for building and testing the NDK. The top level
`checkbuild.py` and `run_tests.py` scripts call into this package.

#### samples

Sample projects to use for non-automated testing.

#### scripts

Additional scripts used for NDK development and release processes. Some of these
scripts may be unfinished or unused, but the development and release
documentation will guide you to the correct ones.

#### sources

Sources for tools and libraries shipped in the NDK that are not maintained in a
separate repository.

#### tests

The NDK's tests. See [Testing.md](Testing.md) for more information.

#### wrap.sh

Premade [wrap.sh](https://developer.android.com/ndk/guides/wrap-script) scripts
for apps.

### prebuilts

Prebuilt toolchains and libraries used or shipped (or both) by the NDK. The LLVM
toolchain we ship is in prebuilts/clang, and the sysroot is in prebuilts/ndk.

### toolchain

Sources for the toolchain and other build components. LLVM lives in
toolchain/llvm-project.

## Core NDK

The NDK components can be loosely grouped into the toolchain (the compiler as
well as its supporting tools and libraries), build systems, and support
libraries.

For more information, see the [Build System Maintainers] guide.

[Build System Maintainers]: docs/BuildSystemMaintainers.md

### Toolchain

The NDK's toolchain is LLVM. This means the NDK uses Clang as its compiler and
the rest of the LLVM suite for other tasks (LLD for linking, llvm-ar for static
library creation, etc).

The toolchain is delivered to the NDK in a prebuilt form via the prebuilts/clang
repositories. The version of the toolchain to be used is defined (at the time of
writing) by `ndk.toolchains.CLANG_VERSION`.

Documentation for using the NDK toolchain can be found in the [Build System
Maintainers] guide. Information on how to update and test the prebuilt toolchain
in the NDK can be found in the [Toolchains](Toolchains.md) guide.

### Build systems

While the NDK is primarily a toolchain for building Android code, the package
also includes some build system support.

First, `$NDK/build/core` contains ndk-build. This is the NDK's home grown build
system. The entry point for this build system is `$NDK/build/ndk-build` (or
`$NDK/build/ndk-build.cmd`).

A CMake toolchain file is included at
`$NDK/build/cmake/android.toolchain.cmake`. This toolchain file configures some
default behaviors and then delegates to the [built-in CMake NDK support], which
in turn allows the NDK to customize some internal behaviors via the hooks in
`$NDK/build/cmake/hooks`. For some configurations, CMake support for the NDK is
entirely implemented in `android-legacy.toolchain.cmake`. Which toolchain is
used by default depends on both the NDK and CMake version, as we will default to
the legacy toolchain file when the new toolchain file has known regressions. To
determine which behavior is the default for a given NDK, check the fallback
condition in `android.toolchain.cmake`.

[built-in CMake NDK support]: https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-android

`$NDK/build/tools/make_standalone_toolchain.py` is a tool which can create a
redistributable toolchain that targets a single Android ABI and API level. As of
NDK r19 it is unnecessary, as the installed toolchain may be invoked directly,
but it remains for compatibility.

Apps and Android libraries (AARs) are typically built by the Gradle using the
Android Gradle Plugin (AGP). AGP uses `externalNativeBuild` tasks to delegate
the native build to either CMake or ndk-build and then handles packaging the
built libraries into the APK. Since the Android Gradle plugin is responsible for
both Java and native code, is not included as part of the NDK.

### Support libraries

`sources/android` and `sources/third_party` contain modules that can be used in
apps (gtest, cpufeatures, native\_app\_glue, etc) via `$(call
import-module,$MODULE)` in ndk-build. CMake modules are not yet available.

## The platform

Most of what NDK users mean when they refer to "the NDK" is actually the C API
surface that is exposed by the OS. These are present in what we consider the NDK
(the zip file we ship) as header files and stub libraries in the sysroot.

Each NDK contains a single set of headers for describing all the API levels it
supports. This means that the same headers are used whether the user's
`minSdkVersion` is 19 or 30, so APIs are annotated with
`__attribute__((available))` so that the compiler can diagnose use of
unavailable APIs.

Stub libraries are provided per supported API level. The stub libraries matching
the user's `minSdkVersion` are used at build time to ensure that apps only use
symbols which are available (though in the future these may be [weak
references](https://github.com/android/ndk/issues/837) to allow apps a more
ergonomic method of conditionally accessing maybe-available APIs). The stub
libraries are **not** packaged in the APK, but instead are loaded from the OS.

Sysroot updates (new system APIs) are delivered to the NDK when an update is
manually triggered. The platform build generates the sysroot, and that artifact
is snapshot in prebuilts/ndk/platform. The prebuilt that is checked in is what
will be shipped.
