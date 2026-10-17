.section .data
msg:    .ascii  "Hello from x86_64!\n"
len = . - msg

.section .text
.global _start

_start:
    mov     $1, %rax        # syscall: write
    mov     $1, %rdi        # fd: stdout
    mov     $msg, %rsi      # buffer
    mov     $len, %rdx      # length
    syscall

    mov     $60, %rax       # syscall: exit
    xor     %rdi, %rdi      # status 0
    syscall
