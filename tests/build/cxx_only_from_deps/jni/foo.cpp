#include <string>

static const std::string kMyString = "foo";

extern "C" const char* foo() {
    return kMyString.c_str();
}
