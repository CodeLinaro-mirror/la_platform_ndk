# Check that if there are no installable modules (i.e. shared libraries
# or executables), ndk-build will automatically build static library
# modules.
$NDK/ndk-build "$@"
if [ "$?" != 0 ]; then
  echo "ERROR: Could not build project!"
  exit 1
fi

# Check that libfoo.a was built properly.
LIBFOO_LIBS=$(find . -name "libfoo.a" 2>/dev/null)
if [ -z "$LIBFOO_LIBS" ]; then
  echo "ERROR: Could not find libfoo.a anywhere:"
  tree .
  exit 1
fi

# Check that libandroid_native_app_glue.a was _not_ built because it was not
# a top-level module, but an imported one.
NATIVE_APP_GLUE_LIBS=$(find . -name "libandroid_native_app_glue.a" 2>/dev/null)
if [ -n "$NATIVE_APP_GLUE_LIBS" ]; then
  echo "ERROR: Should not find libandroid_native_app_glue.a in output directory:"
  tree .
  exit 1
fi

