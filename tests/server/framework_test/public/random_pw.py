import random
import string
import re


# Started by AICoder, pid:e4ff5v9616tde001405c0b73d056cb330ea43e39
def random_pw(length=12):
    # 定义字符集
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    symbols = string.punctuation

    # 确保密码包含至少一个大小写字母、数字和特殊字符
    password = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digits),
        random.choice(symbols)
    ]

    # 剩余部分随机选择，确保不超过2个连续相同字符
    remaining_length = length - 4
    all_chars = lower + upper + digits + symbols

    for _ in range(remaining_length):
        # 尝试选择一个字符，确保不会产生超过2个连续相同字符
        max_attempts = 100
        for _ in range(max_attempts):
            char = random.choice(all_chars)
            # 检查添加这个字符后是否会产生超过2个连续相同字符
            test_password = ''.join(password) + char
            if not re.search(r'(.)\1\1', test_password):
                password.append(char)
                break
        else:
            # 如果尝试多次都失败，选择一个与最后两个字符不同的字符
            if len(password) >= 2:
                last_two = ''.join(password[-2:])
                available_chars = [c for c in all_chars if c not in last_two]
                if available_chars:
                    password.append(random.choice(available_chars))
                else:
                    password.append(random.choice(all_chars))
            else:
                password.append(random.choice(all_chars))

    # 打乱密码以确保随机性（但保持不包含超过2个连续相同字符）
    # 重新生成以确保满足要求
    final_password = ''.join(password)
    while re.search(r'(.)\1\1', final_password):
        random.shuffle(password)
        final_password = ''.join(password)
        # 如果打乱后仍有问题，修复连续字符
        final_password = _fix_consecutive_chars(final_password, all_chars)

    return final_password


def _fix_consecutive_chars(password, all_chars):
    """修复密码中超过2个连续相同字符的问题"""
    result = list(password)
    i = 0
    while i < len(result) - 2:
        if result[i] == result[i + 1] == result[i + 2]:
            # 找到连续3个相同字符，替换中间的那个
            # 选择一个与前后都不同的字符
            available = [c for c in all_chars if c != result[i]]
            if available:
                result[i + 1] = random.choice(available)
        i += 1
    return ''.join(result)
# Ended by AICoder, pid:e4ff5v9616tde001405c0b73d056cb330ea43e39
