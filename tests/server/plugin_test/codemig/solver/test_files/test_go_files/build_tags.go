//go:build (amd64 && go1.17 && !go1.25) || (arm64 && go1.20 && !go1.25)
// +build amd64,go1.17,!go1.25 arm64,go1.20,!go1.25
// +build go1.18
// riscv64应不在匹配范围内
// +build riscv64,go1.17,!go1.25 arm64,go1.20,!go1.25
//go:build riscv64,go1.17,!go1.25 arm64,go1.20,!go1.25