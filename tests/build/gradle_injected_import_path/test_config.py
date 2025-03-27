from pathlib import Path
from typing import List


THIS_DIR = Path(__file__).parent.resolve()


def extra_ndk_build_flags() -> List[str]:
    return [f"NDK_GRADLE_INJECTED_IMPORT_PATH={THIS_DIR}"]
