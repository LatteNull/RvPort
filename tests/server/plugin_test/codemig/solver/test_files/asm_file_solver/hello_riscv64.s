.section .data
msg:    .ascii "Hello from RISC-V!\n"
len = . - msg

.section .text
.global _start

_start:
    li      a7, 64          # syscall: write
    li      a0, 1           # fd: stdout
    la      a1, msg         # buffer
    li      a2, len         # length
    ecall

    li      a7, 93          # syscall: exit
    li      a0, 0           # status 0
    ecall
