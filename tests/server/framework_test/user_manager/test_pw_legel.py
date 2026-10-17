from common.response.response_code import ResponseCode
from framework.user_manager.user_manager import _check_pwd_rule


def test_type_error():
    status, code = _check_pwd_rule('', 'test')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL


def test_less_than_8():
    status, code = _check_pwd_rule('1234ASd', 'test')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL


def test_over64():
    status, code = _check_pwd_rule('1234ASd890' * 6 + '12345', 'test')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL


def test_less_2_class():
    status, code = _check_pwd_rule('1234ASDF', 'test')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL


def test_less_1_class():
    status, code = _check_pwd_rule('12345678', 'test')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_ILLEGAL


def test_less_3_class():
    status, code = _check_pwd_rule('1234ABCa', 'test')
    assert status is True


def test_less_4_class():
    status, code = _check_pwd_rule('1234ABCa@', 'test')
    assert status is True


def test_char():
    pwd = r'~!@#$%^&*()_-=+\|[{}];:\'",<.>/?Ab'
    status, code = _check_pwd_rule(pwd, 'test')
    assert status is True


def test_less_consecutivechar():
    status, code = _check_pwd_rule('1234ASDDDFf', 'test')
    assert status is False
    assert code == ResponseCode.CONSECUTIVE_CHAR_ERROR_CODE


def test_has_username():
    status, code = _check_pwd_rule('1234ASDFf', '1234ASDFf')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_HASUSERNAME
    status, code = _check_pwd_rule('1234ASDFf1234ASDFf', '1234ASDFf')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_USERNAME_2
    status, code = _check_pwd_rule('fFDSA4321', '1234ASDFf')
    assert status is False
    assert code == ResponseCode.USER_PASSWORD_USERNAME_REVERSE
