# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Text colorer for use with TextResult which uses Rich color tags."""


def rich_text_colorer(text: str, color: str, do_color: bool) -> str:
    if do_color:
        return f"[{color}]{text}[/{color}]"
    return text
