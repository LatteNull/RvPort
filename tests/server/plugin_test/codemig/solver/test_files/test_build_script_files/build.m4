dnl 检查 x86 特性
AC_DEFUN([CHECK_X86_FEATURES], [
    AS_IF([test "$host_cpu" = "i386"], [enable_x86=yes])
])