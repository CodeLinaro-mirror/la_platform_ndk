def run_unsupported(test, device):
    # The tested behavior fails reliably on API 16, but it's flaky on 24, so
    # skip the test until 26 where it appears reliable.
    if test.executable == "googletest-death-test-test" and device.version < 26:
        bug = "https://github.com/android-ndk/ndk/issues/795"
        return f"android-{device.version} ({bug})"
    return None
