# Testing the NDK

The latest version of this document is available at
https://android.googlesource.com/platform/ndk/+/master/docs/Testing.md.

The NDK tests are built as part of a normal build (with `checkbuild.py`) and run
with `run_tests.py`. See [Building.md] for more instructions on building the
NDK.

[Building.md]: Building.md

## Prerequisites

1. `adb` must be in your `PATH`.
2. You must have compatible devices connected. See the "Devices and Emulators"
   section.

## tl;dr

If you don't care how this works (if you want to know how this works, sorry, but
you're going to have to read the whole thing) and just want to copy paste
something that will build and run all the tests:

```bash
# In the //ndk directory of an NDK `repo init` tree.
$ poetry shell
$ ./checkbuild.py  # Build the NDK and tests.
$ ./run_tests.py  # Pushes the tests to test devices and runs them.
```

**Pay attention to the warnings.**  Running tests requires that the correct set
of devices are available to adb. If the right devices are not available, **your
tests will not run**.

### Typical test cycle for fixing a bug

This section describes the typical way to test and fix a bug in the NDK.

```bash
# All done from //ndk, starting from a clean tree.
# 1. Update your tree.
$ repo sync
# 2. Create a branch for development.
$ repo start $BRANCH_NAME_FOR_BUG_FIX .
# 3. Make sure your python dependencies are up to date.
$ poetry install
# 4. Enter the poetry environment. You can alternatively prefix all python
# commands below with `poetry run`.
$ poetry shell
# 5. Build the NDK and tests.
$ ./checkbuild.py
# 6. Run the tests to make sure everything is passing before you start changing
# things.
$ ./run_tests.py
# 7. Write the regression test for the bug. The new rest of the instructions
# will assume your new test is called "new_test".
# 8. Build and run the new test to make sure it catches the bug. The new test
# should fail. If it doesn't, either your test is wrong or the bug doesn't
# exist.
#
# We use --rebuild here because run_tests.py does not build tests by default,
# since that's usually a waste of time (see below). We use --filter to ignore
# everything except our new test.
$ ./run_tests.py --rebuild --filter new_test
# 9. Attempt to fix the bug.
# 10. Rebuild the affected NDK component. If you don't know which component you
# altered, it's best to just build the whole NDK again
# (`./checkbuild.py --no-build-tests)`. One case where you can avoid a full
# rebuild is if the fix is contained to just ndk-build or CMake. We'll assume
# that's the case here.
$ ./checkbuild.py --no-build-tests ndk-build
# 11. Re-build and run the test with the supposedly fixed NDK.
$ ./run_tests.py --rebuild --filter new_test
# If the test fails, return to step 9. Otherwise, continue.
# 12. Rebuild and run *all* the tests to check that your fix didn't break
# something else. If you only rebuilt a portion of the NDK in step 10, it's best
# to do a full `./checkbuild.py` here as well (either use `--no-build-tests` or
# omit `--rebuild` for `run_tests.py` to avoid rebuilding all the tests
# *twice*).
$ ./run_tests.py --rebuild
# If other tests fail, return to step 9. Otherwise, continue.
# 13. Commit and upload changes. Don't forget to `git add` the new test!
```

## Types of tests

The NDK has a few different types of tests. Each type of test belongs to its own
"suite", and these suites are defined by the directories in `//ndk/tests`.

### Build tests

Build tests are the tests in [//ndk/tests/build]. These exercise the build
systems and compilers in ways where it is not important to run the output of the
build; all that is required for the test to pass is for the build to succeed.

For example, [//ndk/tests/build/cmake-find_library] verifies that CMake's
`find_library` is able to find libraries in the Android sysroot. If the test
builds, the feature under test works. We could also run the executable it builds
on the connected devices, but it wouldn't tell us anything interesting about
that feature, so we skip that step to save time.

#### Test subtypes

Because the test outputs of build tests do not need to be run, build tests have
a few subtypes that can test more flexibly than other test types. These are
`test.py` and `build.sh` tests.

One test directory can be used as more than one type of test. This is quite
common when a behavior should be tested in both CMake and ndk-build.

The test types in a directory are determined as follows (in order of
precedence):

1. If there is a `build.sh` file in the directory, it is a `build.sh` test. No
   other test types will be considered.
2. If there is a `test.py` file in the directory, it is a `test.py` test. No
   other test types will be considered.
3. If there are files matching `jni/*.mk` in the directory, it is an ndk-build
   test. These tests may co-exist with CMake tests.
4. If there is a `CMakeLists.txt file in the directory, it is a CMake test.
   These tests may co-exist with ndk-build tests.

[//ndk/tests/build]: ../tests/build
[//ndk/tests/build/cmake-find_library]: ../tests/build/cmake-find_library

##### ndk-build

An ndk-build test will treat the directory as an ndk-build project.
`ndk-build` will build the project for each configuration.

##### CMake

A CMake test will treat the directory as a CMake project. CMake will configure
and build the project for each configuration.

##### test.py

A `test.py` build test allows the test to customize its execution and results.
It does this by delegating those details to the `test.py` script in the test
directory. Any (direct) subdirectory of `//ndk/tests/build` that contains a
`test.py` file will be executed as this type of test.

**These types of tests are rarely needed.** Unless you need to inspect the
output of the build, need to build in a very non-standard way, or need to test
a behavior outside CMake or ndk-build, you probably do not want this type of
test.

For example, [//ndk/tests/build/NDK_ANALYZE] builds an ndk-build project that
emits clang static analyzer warnings that the test then checks for.

For some commonly reused `test.py` patterns, there are helpers in [ndk.testing]
that will simplify writing these forms of tests. Verifying that the build system
passes a specific flag to the compiler when building is a common pattern, such
as in [//ndk/tests/build/branch-protection].

[//ndk/tests/build/NDK_ANALYZE]: ../tests/build/NDK_ANALYZE
[ndk.testing]: ../ndk/testing
[//ndk/tests/build/branch-protection]: ../tests/build/branch-protection

##### build.sh

A `build.sh` test is similar to a `test.py` test, but with a worse feature set
in a worse language, and also can't be tested on Windows. Do not write new
`build.sh` tests. If you need to modify an existing `build.sh` test, consider
migrating it to `test.py` first.

#### Negative build tests

Most build tests cannot easily check negative test cases, since they typically
are only verified by the exit status of the build process (`build.sh` and
`test.py` tests can of course do better). To make a negative test for an
ndk-build or CMake build test, use the `is_negative_test` `test_config.py`
option:

```python
def is_negative_test() -> bool:
    return True
```

#### Passing additional command line arguments to build systems

For tests that need to pass specific command line arguments to the build system,
use the `extra_cmake_flags` and `extra_ndk_build_flags` `test_config.py`
options:

```python
def extra_cmake_flags() -> list[str]:
    return ["-DANDROID_STL=system"]


def extra_ndk_build_flags() -> list[str]:
    return ["NDK_GRADLE_INJECTED_IMPORT_PATH=foo"]
```

### Device tests

Device tests are the tests in [//ndk/tests/device]. Device tests inherit most of
their behavior from build tests. It differs from build tests in that the
executables that are in the build output will be run on compatible attached
devices (see "Devices and Emulators" further down the page).

These test will be built in the same way as build tests are, although `build.sh`
and `test.py` tests are not valid for device tests. Each executable in the
output directory of the build will be treated as a single test case. The
executables and shared libraries in the output directory will all be pushed to
compatible devices and run.

[//ndk/tests/build]: ../tests/device

### libc++ tests

libc++ tests are the tests in [//ndk/tests/libc++]. These are a special case of
device test that are built by LIT (LLVM's test runner) rather than ndk-build or
CMake, and the test sources are in the libc++ source tree.

As with device tests, executables and shared libraries in the output directory
will be pushed to the device to be run. The directory structure differs from our
device tests though because some libc++ tests are sensitive to that. Some tests
also contain test data that will be pushed alongside the binaries.

You will never write one of these tests in the NDK. If you need to add a test to
libc++, do it in the upstream LLVM repository. You probably do not need to
continue reading this section unless you are debugging libc++ test failures or
test runner behavior.

There is only one "test" in the libc++ test directory. This is not a real test,
it is just a convenience for the test scanner. The test builder will invoke LIT
on the libc++ test directory, which will build all the libc++ tests to the test
output directory. This will emit an xunit report that the test builder parses
and converts into new "tests" that do nothing but report the result from xunit.
This is a hack that makes the test results more readable.

[//ndk/tests/build]: ../tests/libc++

### ndk-stack

These are typic Python tests that use the `unittest` library to exercise
ndk-stack. Unlike all the other tests in the NDK, these are not checked by
`checkbuild.py` or `run_tests.py`. To run these tests, run:

```bash
poetry run pytest tests/ndk-stack/*.py
```

## Controlling test build and execution

### Re-building tests

**The tests will not be rebuilt unless you use `--rebuild`.** `run_tests.py`
will not _build_ tests unless it is specifically requested because doing so is
expensive. If you've changed something and need to rebuild the test, use
`--rebuild` as well as `--filter`.

### Running a subset of tests

To re-check a single test during development, use the `--filter` option of
`run_tests.py`. For example, `poetry run ./run_tests.py --filter math` will re-
run the math tests.

To run more than one test, the `--filter` argument does support shell-like
globbing. `--filter "emutls-*"` will re-run the tests that match the pattern
`emultls-*`, for example.

Keep in mind that `run_tests.py` will not rebuild tests by default. If you're
iterating on a single test, you probably need the `--rebuild` flag described
above to rebuild the test after any changes.

### Restricting test configurations

By default, every variant of the test will be run (and, if using `--rebuild`,
built). Some test matrix dimensions can be limited to speed up debug iteration.
If you only need to debug 64-bit Arm, for example, pass `--abi arm64-v8a` to
`run_tests.py`.

The easiest way to prevent tests from running on API levels you don't want to
re-check is to just unplug those devices. Alternatively, you can modify
`qa_config.json` to remove those API levels.

Other test matrix dimensions (such as build system or CMake toolchain file
variant) cannot currently be filtered.

### Showing all test results

By default `run_tests.py` will only show failing tests. Failing means either
tests that are expected to pass but failed, or were expected to fail but passed.
Tests that pass, were skipped due to an invalid configuration, or failed but
have been marked as a known failure will not be shown unless the `--show-all`
flag is used. This is helpful for checking that your test really did run rather
than being skipped, or to verify that your `test_config.py` is correctly
identifying a known failure.

## Testing Releases

When testing a release candidate, your first choice should be to run the test
artifacts built on the build server for the given build. This is the
ndk-tests.tar.bz2 artifact in the same directory as the NDK zip. Extract the
tests somewhere, and then run:

```bash
$ ./run_tests.py --clean-device path/to/extracted/tests
```

`--clean-device` is necessary to ensure that the new tests do get pushed to the
device even if the timestamps on the tests are older than what's currently
there. If you need to re-run those tests (say, to debug a failing test), you
will want to omit `--clean-device` for each subsequent run of the same test
package or each test run will take a very long time.

The ndk-tests.tar.bz2 artifact will exist for each of the "linux", "darwin_mac",
and "win64_tests" targets. All of them must be downloaded and run. Running only
the tests from the linux build will not verify that the windows or darwin NDKs
produces usable binaries.

## Broken and Unsupported Tests

To mark tests as currently broken or as unsupported for a given configuration,
add a `test_config.py` to the test's root directory (in the same directory as
`jni/`).

Unsupported tests will not be built or run. They will show as "SKIPPED" if you
use `--show-all`. Tests should be marked unsupported for configurations that do
not work **when failure is not a bug**. For example, yasm is an x86 only
assembler, so the yasm tests are unsupported for non-x86 ABIs.

Broken tests will be built and run, and the result of the test will be inverted.
A test that fails will become an "EXPECTED FAILURE" and not be counted as a
failure, whereas a passing test will become an "UNEXPECTED SUCCESS" and count as
a failure. Tests should be marked broken **when they are known to fail and that
failure is a bug to be fixed**. For example, at the time of writing, ASan
doesn't work on API 21. It's supposed to, so this is a known bug.

By default, `run_tests.py` will hide expected failures from the output since the
caller is most likely only interested in seeing what effect their change had. To
see the list of expected failures, pass `--show-all`.

"Broken" and "unsupported" come in both "build" and "run" variants. This allows
better fidelity for describing a test that is known to fail at runtime, but
should build correctly. Such a test would use `run_broken` rather than
`build_broken`.

Here's an example `test_config.py` that marks the tests in the same directory as
broken when building for arm64 and unsupported when running on a pre-Lollipop
device:

```python
from typing import Optional

from ndk.test.devices import Device
from ndk.test.types import Test


def build_broken(test: Test) -> tuple[Optional[str], Optional[str]]:
    if test.abi == 'arm64-v8a':
        return test.abi, 'https://github.com/android-ndk/ndk/issues/foo'
    return None, None


def run_unsupported(test: Test, device: Device) -> Optional[str]:
    if device.version < 21:
        return f'{device.version}'
    return None
```

The `*_broken` checks return a tuple of `(broken_configuration, bug_url)` if the
given configuration is known to be broken, else `(None, None)`. All known
failures must have a (public!) bug filed. If there is no bug tracking the
failure yet, file one on GitHub.

The `*_unsupported` checks return `broken_configuration` if the given
configuration is unsupported, else `None`.

The configuration is available in the `Test` and `Device` objects which are
arguments to each function. Check the definition of each class to find which
properties can be used, but the most commonly used are:

* `test.abi`: The ABI being built for.
* `test.api`: The platform version being *built* for. Not necessarily the
  platform version that the test will be run on.
* `device.version`: The API level of the device the test will be run on.
* `test.name`: The full name of the test, as would be reported by the test
  runner. For example, the `fuzz_test` executable built by `tests/device/fuzzer`
  is named `fuzzer.fuzz_test`. Build tests should never need to use this
  property, as there is only one test per directory. libc++ tests will most
  likely prefer `test.case_name` (see below).
* `test.case_name`: The shortened name of the test case. This property only
  exists for device tests (for `run_unsupported` and `run_broken`). This
  property will not exactly match the name of the executable. If the executable
  is named `foo.pass.cpp.exe`, but `test.case_name` will be `foo.pass`.

## Devices and Emulators

For testing a release, make sure you're testing against the released user builds
of Android.

For Nexus/Pixel devices, use https://source.android.com/docs/setup/build/flash
(Googlers, use http://go/flash). Factory images are also available here:
https://developers.google.com/android/nexus/images.

For emulators, use emulator images from the SDK rather than from a platform
build, as these are what our users will be using. Note that some NDK tests
(namely test-googletest-full and asan-smoke) are known to break between emulator
updates. It is not known whether these are NDK bugs, emulator bugs, or x86_64
system image bugs. Just be aware of them, and update the test config if needed.

After installing the emulator images from the SDK manager, they can be
configured and launched for testing with (assuming the SDK tools directory is in
your path):

```bash
$ android create avd --name $NAME --target android-$LEVEL --abi $ABI
$ emulator -avd $NAME
```

This will create and launch a new virtual device.

Whether physical devices or emulators will be more useful depends on your host
OS.

For an x86_64 host, physical devices for the Arm ABIs will be much faster than
emulation. x86/x86_64 emulators will be virtualized on x86_64 hosts, which are
very fast.

For M1 Macs, it is very difficult to test x86/x86_64, as devices with those ABIs
are very rare, and the emulators for M1 Macs are also Arm. For this reason, it's
easiest to use an x86_64 host for testing x86/x86_64 device behavior.

### Device selection

`run_tests.py` will only consider devices that match the configurations
specified by `qa_config.json` when running tests. We do not test against every
supported version of the OS (as much as I'd like to, my desk isn't big enough
for that many phones), but only the subset specified in that file.

Any connected devices that do not match the configurations specified by
`qa_config.json` will be ignored. Devices that match the tested configs will be
pooled to allow sharding.

Each test will be run on every device that it is compatible with. For example,
a test that was built for armeabi-v7a with a minSdkVersion of 21 will run on all
device pools that support that ABI with an OS API level of 21 or newer (unless
otherwise disabled by `run_unsupported`).

**Read the warnings printed at the top of `run_tests.py` output to figure out
what device configurations your test pools are missing.** If any warnings are
printed, the configuration named in the warning **will not be tested**. This is
a warning rather than an error because it is very common to not have all
configurations available (as mentioned above, it's not viable for M1 Macs to
check x86 or x86_64). If you cannot test every configuration, be aware of what
configurations your changes are likely to break and make sure those are at least
tested. When testing a release, make sure that all configurations have been
tested before shipping.

`qa_config.json` has the following format:

```json
{
  "devices": {
    "21": [
      "armeabi-v7a",
      "arm64-v8a"
    ],
    "32": [
      "armeabi-v7a",
      "arm64-v8a",
      "x86_64"
    ]
  }
}
```

The `devices` section specifies which types of devices should be used for
running tests. Each key defines the OS API level that should be tested, and the
value is a list of ABIs that should be checked for that OS version. In the
example above, tests will be run on each of the following device configurations:

* API 21 armeabi-v7a
* API 21 arm64-v8a
* API 32 armeabi-v7a
* API 32 arm64-v8a
* API 32 x86_64

The format also supports the infrequently used `abis` and `suites` keys. **You
probably do not need to read this paragraph.** Each has a list of strings as the
value. Both can be used to restrict the build configurations of the tests.
`abis` selects which ABIs to build. This property will be overridden by `--abis`
if that argument is used, and will default to all ABIs if neither are present,
which is the normal case. `suites` selects which test suites to build. Valid
entries in this list are the directory names within `tests`, with the exception
of `ndk-stack`. In other words (at the time of writing), `build`, `device`, and
`libc++` are valid items.

## Windows VMs

Warning: the process below hasn't been tested in a very long time. Googlers
should refer to http://go/ndk-windows-vm for slightly more up-to-date Google-
specific setup instructions, but http://go/windows-cloudtop may be easier.

Windows testing can be done on Windows VMs in Google Compute Engine. To create
one:

* Install the [Google Cloud SDK](https://cloud.google.com/sdk/).
* Run `scripts/create_windows_instance.py $PROJECT_NAME $INSTANCE_NAME`
    * The project name is the name of the project you configured for the VMs.
    * The instance name is whatever name you want to use for the VM.

This process will create a `secrets.py` file in the NDK project directory that
contains the connection information.

The VM will have Chrome and Git installed and WinRM will be configured for
remote command line access.

TODO: Implement `run_tests.py --remote-build`.
