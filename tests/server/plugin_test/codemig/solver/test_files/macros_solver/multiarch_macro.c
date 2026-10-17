#if (VSAN_ARCH == x86_64)
static inline unsigned long dp_bit_ffz(unsigned long long_word)
{

        return long_word;
}
#endif

#if (VSAN_ARCH == aarch64)
static inline unsigned long dp__ffs(unsigned long word)
{
    return __builtin_ctzl(word);
}
#define dp_bit_ffz(x)  dp__ffs(~(x))
#endif

#if (VSAN_ARCH == __ppc__)
static inline static inline unsigned long dp__ffs(unsigned long word)
{
    return "not support";
}
#endif