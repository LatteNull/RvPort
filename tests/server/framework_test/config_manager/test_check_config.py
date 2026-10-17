from framework.user_manager.user_db import Role
from unittest.mock import patch, MagicMock
import pytest
from framework.config_manager.config_manager import check_and_update, ResponseCode, \
    list_user_config, check_usr_admin_role  # 假设ResponseCode也在同一个模块中定义或导入

def test_check_and_update_with_non_admin():
    # 测试非管理员用户调用时的行为
    with patch('framework.config_manager.config_manager.check_usr_admin_role', return_value=(False, ResponseCode.NON_PRIVILEGED)):
        key = 'test_key'
        value = 'test_value'
        op_usr_id = 'non_admin_user'
        result = check_and_update(key, value, op_usr_id)
        assert result == (False, ResponseCode.NON_PRIVILEGED), "非管理员用户应返回错误"

def test_check_and_update_with_admin_success():
    # 测试管理员用户更新配置成功的情况
    with patch('framework.config_manager.config_manager.check_usr_admin_role', return_value=(True, None)), \
         patch('framework.config_manager.config_manager.SysConfig.update', return_value=(True, ResponseCode.OK)):
        key = 'test_key'
        value = 'test_value'
        op_usr_id = 'admin_user'
        result = check_and_update(key, value, op_usr_id)
        assert result == (True, ResponseCode.OK), "管理员用户更新配置应成功"

def test_check_and_update_with_admin_failure():
    # 测试管理员用户更新配置失败的情况
    with patch('framework.config_manager.config_manager.check_usr_admin_role', return_value=(True, None)), \
         patch('framework.config_manager.config_manager.SysConfig.update', side_effect=Exception("Update failed")):
        key = 'test_key'
        value = 'test_value'
        op_usr_id = 'admin_user'
        try:
            check_and_update(key, value, op_usr_id)
        except Exception as e:
            assert str(e) == "Update failed", "更新失败时应该抛出异常"

def test_list_user_config_with_non_admin():
    # 非管理员用户：能查询，但只返回网络代理相关配置
    with patch('framework.config_manager.config_manager.check_usr_admin_role', return_value=(False, ResponseCode.NON_PRIVILEGED)), \
         patch('framework.config_manager.config_manager.SysConfig.list_all',
               return_value=(True, None, {
                   'docker_http_proxy': 'http://proxy:3128',
                   'docker_https_proxy': 'http://proxy:3128',
                   'docker_no_proxy': 'localhost',
                   'max_online_users': '10',
               })):
        op_usr_id = 'non_admin_user'
        ip = '192.168.1.1'
        success, code, config_set = list_user_config(op_usr_id, ip)
        assert success is True, "非管理员用户应能查询代理配置"
        assert set(config_set.keys()) == {'docker_http_proxy', 'docker_https_proxy', 'docker_no_proxy'}, \
            "非管理员用户只能看到网络代理相关配置"

def test_list_user_config_with_admin_success():
    # 测试管理员用户查询配置成功的情况
    with patch('framework.config_manager.config_manager.check_usr_admin_role', return_value=(True, None)), \
         patch('framework.config_manager.config_manager.SysConfig.list_all', return_value=(True, None, {'key1': 'value1', 'key2': 'value2'})):
        op_usr_id = 'admin_user'
        ip = '192.168.1.1'
        result = list_user_config(op_usr_id, ip)
        assert result == (True, None, {'key1': 'value1', 'key2': 'value2'}), "管理员用户查询配置应成功"

def test_check_usr_admin_role_with_none_user_id():
    # 测试传入 None 作为用户ID的情况
    result = check_usr_admin_role(op_usr_id=None)
    assert result == (False, ResponseCode.NON_PRIVILEGED), "传入 None 作为用户ID应返回错误"

def test_check_usr_admin_role_with_nonexistent_user():
    # 测试不存在的用户ID
    with patch('framework.config_manager.config_manager.UserManager.query_by_id', return_value=None):
        op_usr_id = 'nonexistent_user'
        result = check_usr_admin_role(op_usr_id)
        assert result == (False, ResponseCode.NON_PRIVILEGED), "不存在的用户ID应返回错误"

def test_check_usr_admin_role_with_non_admin_user():
    # 测试非管理员用户
    with patch('framework.config_manager.config_manager.UserManager.query_by_id', return_value=MagicMock(role=Role.NORMAL)):
        op_usr_id = 'non_admin_user'
        result = check_usr_admin_role(op_usr_id)
        assert result == (False, ResponseCode.NON_PRIVILEGED), "非管理员用户应返回错误"

def test_check_usr_admin_role_with_admin_user():
    # 测试管理员用户
    with patch('framework.config_manager.config_manager.UserManager.query_by_id', return_value=MagicMock(role=Role.ADMIN)):
        op_usr_id = 'admin_user'
        result = check_usr_admin_role(op_usr_id)
        assert result == (True, None), "管理员用户应返回成功"

