# Working with the NDK Toolchains

The latest version of this document is available at
https://android.googlesource.com/platform/ndk/+/master/docs/Toolchains.md.

The LLVM toolchain shipped in the NDK is not built as a part of the NDK build
process. Instead is it built separately and checked into git as a prebuilt that
is repackaged when shipped in the NDK.

An artifact of the toolchain build is the distribution tarball. That artifact is
unpacked into a location in the Android tree and checked in. The NDK build step
for the toolchain copies that directory into the NDK and makes some
modifications to make the toolchains suit the NDK rather than the platform.
For example, non-NDK runtime libraries are deleted and the NDK sysroot is
installed to the `sysroot` subdirectory of the toolchain so it can be found
automatically by the compiler.

Note: Any changes to either toolchain need to be tested in the platform *and*
the NDK. The platform and the NDK both get their toolchains from the same build.

TODO: This process is far too manual. `checkbuild.py` should be updated (or
additional scripts added) to ease this process.

## Clang

Clang's build process is described in the [Android LLVM Readme]. Note that Clang
cannot be built from the NDK tree. The output tarball is extracted to
`prebuilts/clang/host/$HOST/clang-$REVISION`. `checkbuild.py toolchain`
repackages this into the NDK out directory.

[Android LLVM Readme]: https://android.googlesource.com/toolchain/llvm_android/+/master/README.md

### Updating to a New Clang

If you're updating the NDK to use a new release of the LLVM toolchain, do the
following.

Note: These steps need to be run after installing the new prebuilt from the
build server to `prebuilts/clang` (see the [update-prebuilts.py]). The LLVM team
will handle installing the new toolchain to prebuilts, but the NDK team usually
makes the change to migrate to the new toolchain as described below.

[update-prebuilts.py]: https://android.googlesource.com/toolchain/llvm_android/+/master/update-prebuilts.py

```bash
# Edit ndk/toolchains.py and update `CLANG_VERSION`.
$ ./checkbuild.py
# ./run_tests.py
```

### Testing local llvm-toolchain changes with the NDK

If you're working with unsubmitted changes to llvm-toolchain and want to test
your LLVM changes in the NDK, do the following. If you're just updating the NDK
to use a newer prebuilt LLVM, you don't need to do this part.

```bash
$ export CLANG_PREBUILTS=`realpath ../prebuilts/clang/host/linux-x86`
$ rm -r $CLANG_PREBUILTS/clang-dev
# $LLVM_TOOLCHAIN refers to the root of your llvm-toolchain source directory. If
# you have a tarball for the toolchain distribution, extract that to
# $CLANG_PREBUILTS/clang-dev instead.
$ cp -r $LLVM_TOOLCHAIN/out/install/$HOST/clang-dev $CLANG_PREBUILTS/
# Update CLANG_VERSION in ndk/toolchains.py to clang-dev.
$ ./checkbuild.py
# Run tests. To run the NDK test suite, you will need to attach the
# appropriately configured devices. The test tool will print warnings for
# missing configurations.
$ ./run_tests.py
```

For details about running tests, see [Testing.md].

[Testing.md]: Testing.md

This installs the new Clang into the prebuilts directory so it can be included
in the NDK.

If you need to make changes to Clang after running the above steps, future
updates can be done more quickly with:

```bash
$ rm -r $CLANG_PREBUILTS/clang-dev
$ tar xf path/to/clang-dev-linux-x86_64.bz2 -C $CLANG_PREBUILTS
$ ./checkbuild.py toolchain
# Run tests.
```

We don't need to rebuild the whole NDK since we've already built most of it.
