from typing import Optional

from ndk.test.devicetest.case import TestCase


def build_unsupported(test: TestCase) -> Optional[str]:
    # Validate if vector types allocate the proper amount of alignment on
    # architectures that support such instructions, when returning large
    # composite types.
    #
    # Some architectures, like 'riscv64' may be excluded if they employ
    # sizeless types. In this case, the vector types are incomplete and
    # cannot be members of unions, classes or structures and must have
    # automatic storage duration. As this particular test requires returning
    # a large composite type and we cannot compose types with other sizeless
    # types, this test can be skipped for the architecture.
    if test.config.abi not in ("armeabi-v7a", "x86", "arm64-v8a", "x86_64"):
        return test.config.abi

    return None
