#
# Copyright (C) 2015 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""APIs for string coloring on ANSI terminals."""

# TODO: Move to ansi.py.


def color_string(string: str, color: str) -> str:
    """Returns a string that will be colored when printed to a terminal."""
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
    }
    end_color = "\033[0m"
    return colors[color] + string + end_color


def maybe_color(text: str, color: str, do_color: bool) -> str:
    """Returns an (optionally) colored string."""
    return color_string(text, color) if do_color else text
