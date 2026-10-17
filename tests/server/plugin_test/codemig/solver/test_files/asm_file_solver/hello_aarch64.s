.section .data
msg:    .ascii "Hello from AArch64!\n"
len = . - msg

.section .text
.global _start

_start:
    mov     x8, #64         // syscall: write
    mov     x0, #1          // fd: stdout
    ldr     x1, =msg        // buffer
    mov     x2, #len        // length
    svc     #0

    mov     x8, #93         // syscall: exit
    mov     x0, #0          // status 0
    svc     #0
