#if defined(SIMDE_X86_AES_NATIVE)
  #include <wmmintrin.h>
#endif

#if defined(HEDLEY_MSVC_VERSION)
  #pragma warning(pop)
#endif

#if !defined(SIMDE_ARM_NEON_A64V8_NATIVE) && !defined(SIMDE_ARM_NEON_A64V8_NO_NATIVE) && !defined(SIMDE_NO_NATIVE)
  #if defined(SIMDE_ARCH_ARM_NEON) && defined(SIMDE_ARCH_AARCH64) && SIMDE_ARCH_ARM_CHECK(8,0)
    #define SIMDE_ARM_NEON_A64V8_NATIVE
  #endif
#endif
#if defined(SIMDE_ARM_NEON_A64V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V8_NATIVE)
  #define SIMDE_ARM_NEON_A32V8_NATIVE
#endif

#if !defined(SIMDE_ARM_NEON_A32V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V8_NO_NATIVE) && !defined(SIMDE_NO_NATIVE)
  #if defined(SIMDE_ARCH_ARM_NEON) && SIMDE_ARCH_ARM_CHECK(8,0) && (__ARM_NEON_FP & 0x02)
    #define SIMDE_ARM_NEON_A32V8_NATIVE
  #endif
#endif
#if defined(__ARM_ACLE)
  #include <arm_acle.h>
#endif
#if defined(SIMDE_ARM_NEON_A32V8_NATIVE) && !defined(SIMDE_ARM_NEON_A32V7_NATIVE)
  #define SIMDE_ARM_NEON_A32V7_NATIVE
#endif