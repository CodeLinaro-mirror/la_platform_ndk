/*
 * Copyright (C) 2011 The Android Open Source Project
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 * COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 * BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
 * OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
 * AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
 * OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

/* A brain-dead 'cmp' toolbox program for Windows, because comp.exe
 * can't be silenced and doesn't return meaningful status code
 */

int main(void)
{
    int argc;
    wchar_t** argv = CommandLineToArgvW(GetCommandLineW(), &argc);

    // Discard the name of the executable.
    if (argc > 0) {
        argc--;
        argv++;
    }

    // IMPORTANT: cmp only accepts optional -s as the first option, followed by two file
    //            name.  Note that regardless of "-s" this cmp always operates in silent mode.
    if (argc > 0 && !wcscmp(argv[0], L"-s")) {
        argc--;
        argv++;
    }
    if (argc != 2) {
        wprintf(L"Usage: cmp [-s] file1 file2\n");
        exit(1);
    }
    const wchar_t* filename1 = argv[0];
    const wchar_t* filename2 = argv[1];
    FILE *f1 = _wfopen(filename1, L"rb");
    if (!f1) {
        wprintf(L"ERROR: can't open file %ls\n", filename1);
        exit(1);
    }
    FILE *f2 = _wfopen(filename2, L"rb");
    if (!f2) {
        wprintf(L"ERROR: can't open file %ls\n", filename2);
        fclose(f1);
        exit(1);
    }
    #define BUFSIZE 4096
    char buf1[BUFSIZE], buf2[BUFSIZE];
    int n1, n2, ret = 0;
    do {
        n1 = fread(buf1, 1, BUFSIZE, f1);
        n2 = fread(buf2, 1, BUFSIZE, f2);
        ret = (n1 != n2) || memcmp(buf1, buf2, n1) != 0;
    } while (!ret && n1 == BUFSIZE);
    fclose(f1);
    fclose(f2);

    return ret;
}
