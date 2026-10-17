import re

OTHER = 0
RISCV = 1

arch_others_word = (r"(x86_64|x86_amd|amd64p32|amd64|"
                    r"arm64be|arm64|armbe|aarch64_be|aarch64|armv8-a|armv8_a|armv8a|armv8|arm9-a|armv9_a|armv9a|armv9|"
                    r"(?<![a-zA-Z0-9])(x86|armv|armx|arm)(?![a-zA-Z0-9]))"
                    )

arch_others_string = ["x86", "arm", "armv8", "armv9"]
arch_like = ['s390', 'mips', 'ppc', 'loong', 'sparc', 'riscv32']
arch_other_pattern = re.compile(arch_others_word)
arch_riscv_word = (r"(riscv64|risc-v|riscv(?!32))")

arch_riscv_string = ["risc-v", "riscv", "riscv64"]

arch_riscv_pattern = re.compile(arch_riscv_word)
isa_others = (
    r"(?<![a-zA-Z0-9])("
    r"avx|avx2|avx512|avx512f|avx512dq|avx512pf|avx512er|avx512cd|avx512bw|avx512vl|avx512ifma|avxifma|avx512vbmi|avx512vbmi|avx512vnni|avx512bitalg|avx512vpopcntdq|"
    r"avx5124fmaps|avx5124vnniw|avx512vp2intersect|sse|avx512vnni|avxvnni|sse2|sse3|ssse3|sse4.1|sse4.2|sse41|sse42|sse4_1|sse4_2|mmx|sse4a|aesni|"
    r"neon_fp16|neon_vfpv4|neon|neon-fp16|neon-vfpv4|sve|neonfp16|neon.fp16|neonvfpv4|neon.vfpv4"
    r")(?![a-zA-Z0-9])"
)

isa_others_string = [
    "avx", "avx2", "avx512", "avx512f", "avx512dq", "avx512pf", "avx512er", "avx512cd", "avx512bw",
    "avx512vl", "avx512ifma", "avxifma", "avx512vbmi", "avx512vbmi",
    "avx512vnni", "avx512bitalg", "avx512vpopcntdq", "avx5124fmaps", "avx5124vnniw",
    "avx512vp2intersect", "sse", "avx512vnni", "avxvnni", "sse2",
    "sse3", "ssse3", "sse4.1", "sse4.2", "sse41", "sse42", "sse4_1", "sse4_2", "mmx", "sse4a",
    "aesni"
    "neon_fp16", "neon_vfpv4", "neon", "neon-fp16", "neon-vfpv4", "sve", "neonfp16", "neon.fp16",
    "neonvfpv4", "neon.vfpv4"
]
isa_other_pattern = re.compile(isa_others)
isa_riscv = (
    r"(?<![a-zA-Z0-9])("
    r"rvv|rv64|rv64g|rv64i|rv128i|zifencei|zihintntl|zihintpause|zicsr|zicntr|zihpm|"
    r"zfh|zfhmin|zma|zfinx|zdinx|zhinx|zhinxmin|ztso|zimop|zicond|zawrs|zacas|rvwmo|zfa|zba|zbb|zbc|zbs|"
    r"zbkb|zbkc|zbkx|zvl32b|zvl64b|zvl128b|zvl256b|zvl512b|zvl1024b|zve32x|zve32f|zve64x|zv64f|zve64d|zvfhmin|zvfh|zknd|zkne|zknh|"
    r"zksed|zksh|zkr|zkn|zks|zk|zkt|rvi|rvm|rvc|rvk|rvb|zvbb|zvbc|zvkb|zvkg|zvkned|zvknh|zvknha|zvknhb|zvksed|zvksh|zvkn|zvknc|zvkng|zvks|zvksc|zvksg|zvkt"
    r")(?![a-zA-Z0-9])"
)

isa_riscv_string = [
    "rvv", "rv64", "rv64g", "rv64gc", "rv64gcv", "rv64i", "rv128i", "zifencei", "zihintntl",
    "zihintpause", "zicsr", "zicntr", "zihpm", "zfh", "zfhmin", "zma", "zfinx", "zdinx",
    "zhinx", "zhinxmin", "ztso", "zimop", "zicond", "zawrs", "zacas", "rvwmo", "zfa", "zba", "zbb",
    "zbc", "zbs", "zbkb", "zbkc", "zbkx", "zvl32b", "zvl64b",
    "zvl128b", "zvl256b", "zvl512b", "zvl1024b", "zve32x", "zve32f", "zve64x", "zv64f", "zve64d",
    "zvfhmin", "zvfh", "zknd", "zkne", "zknh", "zksed", "zksh",
    "zkr", "zkn", "zks", "zk", "zkt", "rvi", "rvm", "rvc", "rvk", "rvb", "zvbb", "zvbc", "zvkb",
    "zvkg", "zvkned", "zvknh", "zvknha", "zvknhb", "zvksed",
    "zvksh", "zvkn", "zvknc", "zvkng", "zvks", "zvksc", "zvksg", "zvkt"
]
instruction_riscv_base = 'gimafdcv'
riscv_base_set = set(instruction_riscv_base)
isa_riscv_pattern = re.compile(isa_riscv)

separators = '_-.#'


def is_rv_arch(name):
    if re.search(arch_riscv_word, name, re.IGNORECASE):
        return True
    return False


def is_other_arch(name):
    if re.search(arch_others_word, name, re.IGNORECASE):
        return True
    return False


def merge_star_sequences(text):
    """
    将 *isa*-*isa*, **_**, **.**, **#** 等合并为 *isa*

    示例：
    **-** → **
    **_#** → **
    **-_.##** → **
    """
    # 匹配 ** 后跟一个或多个分隔符 (-_. #)，再跟 **
    pattern = rf'\*isa\*[{separators.replace('-', '\\-')}]\*isa\*'
    while 10:
        # 替换为单个 **
        if re.search(pattern, text):
            text = re.sub(pattern, '*isa*', text)
        else:
            break
    return text


def extract_pattern_and_remainder(pattern, name: str, replace='arch'):
    if not name:
        return False, None, None
    match = re.search(pattern, name)
    if not match:
        return False, None, name
    # 从原始字符串中移除所有匹配的架构
    matched_text = match.groups()
    remainder = re.sub(pattern, f'*{replace}*', name)
    if replace == 'isa':
        remainder = merge_star_sequences(remainder)
    return True, matched_text, remainder


def has_arch_and_remainder(name):
    match_arch, match, remainder_other = extract_pattern_and_remainder(arch_other_pattern, name,
                                                                       'arch')
    match_isa, match2, remainder_other = extract_pattern_and_remainder(isa_other_pattern,
                                                                       remainder_other, 'isa')
    match_other = match_arch or match_isa
    match_arch, match, remainder_rv = extract_pattern_and_remainder(arch_riscv_pattern, name,
                                                                    'arch')
    match_isa, match2, remainder_rv = extract_pattern_and_remainder(isa_riscv_pattern, remainder_rv,
                                                                    'isa')
    if match2 == 'zk' and not match_arch:
        match_isa = False
        remainder_rv = name
    match_riscv = match_arch or match_isa

    if match_other and not match_riscv:
        return True, OTHER, remainder_other
    elif match_riscv:
        return True, RISCV, remainder_rv
    return False, OTHER, name
