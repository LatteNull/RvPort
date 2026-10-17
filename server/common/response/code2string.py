from .response_code import ResponseCode

Code2String = {
    ResponseCode.USER_NAME_DUPLICATE: 'username already exists',
    ResponseCode.USER_PASSWORD_HASUSERNAME: 'The password cannot contain the user name',
    ResponseCode.USER_SAVEDB_ERROR: 'db save error',
    ResponseCode.USER_NAME_ILLEGAL: 'the username contains illegal characters',
    ResponseCode.USER_PASSWORD_ILLEGAL: 'password contains illegal characters',
    ResponseCode.USER_PASSWORD_WEAK: 'password is weak',
    ResponseCode.PW_TIMEOUT: 'password is expired',
    ResponseCode.USER_FIRST_LOGIN: 'Password change required at first login',
    ResponseCode.USER_PASSWORD_NOCHANGE: 'password is the same as old password',
    ResponseCode.USER_HISTORY_PW: 'New password cannot be the same as any of your last two passwords',
    ResponseCode.USER_AUTH_FAILED: 'Authentication failed',
    ResponseCode.IP_LOCKED: 'IP locked',
    ResponseCode.CANNOT_DEL_ADMIN: 'Admin user cannot be deleted',
    ResponseCode.USER_NOT_EXIST: 'User not exist',
    ResponseCode.USER_PASSWORD_USERNAME_REVERSE: 'The password cannot be the reverse of the user name',
    ResponseCode.USER_PASSWORD_USERNAME_2: 'The password cannot be two consecutive repetitions of the user name',
    ResponseCode.USER_OVER_MAX_ONLINE: 'Maximum number of online users reached.'

}

Code2String_zh = {
    ResponseCode.USER_NAME_DUPLICATE: '已存在同名用户',
    ResponseCode.USER_PASSWORD_HASUSERNAME: '密码不能包含用户名',
    ResponseCode.USER_SAVEDB_ERROR: '数据库异常',
    ResponseCode.USER_NAME_ILLEGAL: '用户名有非法字符',
    ResponseCode.USER_PASSWORD_ILLEGAL: '密码有非法字符',
    ResponseCode.USER_PASSWORD_WEAK: '弱密码',
    ResponseCode.PW_TIMEOUT: '密码过期',
    ResponseCode.USER_FIRST_LOGIN: '第一次登录，需要先修改密码',
    ResponseCode.USER_PASSWORD_NOCHANGE: '密码和旧密码相同',
    ResponseCode.USER_HISTORY_PW: '新密码与近期使用过的密码重复',
    ResponseCode.USER_AUTH_FAILED: '认证失败',
    ResponseCode.IP_LOCKED: 'IP被锁定',
    ResponseCode.CANNOT_DEL_ADMIN: '不能删除Admin用户',
    ResponseCode.USER_NOT_EXIST: '用户不存在',
    ResponseCode.USER_PASSWORD_USERNAME_REVERSE: '密码不能是用户名的逆序',
    ResponseCode.USER_PASSWORD_USERNAME_2: '不能是用户名的二次重复',
    ResponseCode.USER_OVER_MAX_ONLINE: '已达到最大在线用户数'
}


def getI18n(code, lan=None):
    if lan == 'zh':
        return Code2String_zh.get(code, code)
    else:
        return Code2String.get(code, code)
