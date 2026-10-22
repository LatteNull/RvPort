#define _7Z_X86 0x03030103
#define BOOT_PLATFORM_X86 0
#if defined(__i386__)
int enabled;
#endif
#if defined(__i386__) || MY_X86_MODE
int unresolved;
#endif

enum class Backend { scalar, avx2 };
int avx2_sum(const int *data);
template<Backend B>
int sum(const int *data) {
    if constexpr (B == Backend::avx2) {
        return avx2_sum(data);
    }
    return 0;
}

enum Sumalg { CKSUM_NONE, CKSUM_SHA512 };
void archive_sha512_update();
void checksum(Sumalg alg) {
    if (alg == CKSUM_SHA512) {
        archive_sha512_update();
    }
}
enum FileFlags { DIRECTORY = 1, CRC32 = 4 };
int read_checksum(int flags) {
    if (flags & CRC32) return 1;
    return 0;
}
int encoded_method(int code) {
    return code == _7Z_X86;
}
int output_platform() {
    return BOOT_PLATFORM_X86;
}
