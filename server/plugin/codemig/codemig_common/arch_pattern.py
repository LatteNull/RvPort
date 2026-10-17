import re

# 文件匹配规则
# 纯架构后缀：base_arm64.go 或 base_arm64.s
arch_pattern = re.compile(
    r'_(x86_64|x86|amd64|arm|arm64|aarch64)(?=\.(go|s)$)'
)


class ArchPattern:

    @staticmethod
    def is_arch_pattern(file):
        # 检查是否为架构文件（如 base_arm64.go）
        return arch_pattern.search(file)

    @staticmethod
    def get_arch_pattern():
        return arch_pattern
