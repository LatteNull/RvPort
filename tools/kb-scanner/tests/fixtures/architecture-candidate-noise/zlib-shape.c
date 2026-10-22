/* Reduced zlib crc32.c/deflate.c shapes; never compiled or executed. */
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRC32) && defined(W)
#define ARMCRC32
#endif
#if defined(__x86_64__) || defined(__aarch64__)
#define W 8
#else
#define W 4
#endif
#ifdef ARMCRC32
unsigned crc(unsigned crc, unsigned long val0) {
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    __asm__ volatile("crc32x %w0, %w0, %x1" : "+r"(crc) : "r"(val0));
    return crc;
}
#endif
__attribute__((no_sanitize("memory"))) void ordinary(void) {}
__attribute__((target("avx2"))) void accelerated(void) {}
void unresolved(void) { __asm__ volatile("vendor_mystery %0" : : "r"(0)); }
