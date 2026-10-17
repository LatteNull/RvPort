AC_CHECK_DECLS([i386], [AC_MSG_ERROR([i386 not supported])])
AC_CHECK_DECLS([x86_64], [AC_DEFINE([HAVE_X86_64], [1])])

case $host_cpu in
  x86_64)
    ARCH_CFLAGS="-march=x86-64"
    ;;
  arm*)
    ARCH_CFLAGS="-march=armv8-a"
    ;;
esac
AC_SUBST([ARCH_CFLAGS])

case $host_cpu in
  x86_64)
    ARCH_CFLAGS="-march=x86-64"
    ;;
  arm*)
    ARCH_CFLAGS="-march=armv8-a"
    ;;
  riscv64)
    ARCH_CFLAGS="-mabi=lp64d"
    ;;
esac
AC_SUBST([ARCH_CFLAGS])

AC_CANONICAL_TARGET
case $target_cpu in
  aarch64)
    CFLAGS="$CFLAGS -march=armv8-a"
    ;;
esac

CFLAGS+="-mavx2 -mfpu=neon"
CFLAGS+="-mfpu=neon"
CFLAGS+="-march=arm"
CFLAGS+="-march=rv"

CFLAGS="-mavx2 -msse4.2 -march=skylake"
AC_DEFINE([WORDS_BIGENDIAN], 1)
AC_DEFINE([WORDS_BIGENDIAN], 0)
AC_DEFINE([WORDS_BIGENDIAN], [1], [Target is big-endian])
AC_DEFINE(ENDIANNESS, 0, [Little-endian system])
AC_DEFINE()

.set arch, armv8-a

__asm__("mov %eax, %ebx");

CC="aarch64-linux-gnu-gcc"

AC_TRY_RUN([arm])
