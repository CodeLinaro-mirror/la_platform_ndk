from typing import Optional

from ndk.abis import LP32_ABIS
from ndk.test.buildtest.case import Test


def build_unsupported(test: Test) -> Optional[str]:
    if test.config.abi in LP32_ABIS:
        return test.config.abi
    return None
