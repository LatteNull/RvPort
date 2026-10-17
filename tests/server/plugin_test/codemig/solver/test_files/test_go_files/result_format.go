//go:build (amd64 && go1.17 && !go1.25) || (arm64 && go1.20 && !go1.25)
// +build amd64,go1.17,!go1.25 arm64,go1.20,!go1.25


/*
#include <stdio.h>

#include <stdlib.h>
void hello() {
    printf("Hello from C");
}
*/
import "C"

runtime . GOARCH == "x86_64"
runtime. GOARCH = "x86_64"