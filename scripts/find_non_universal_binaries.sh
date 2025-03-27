#!/usr/bin/env bash
! find "${1:-.}" -type f -print0 | xargs -0 file | grep "Mach-O" | grep -v "Mach-O universal binary"
