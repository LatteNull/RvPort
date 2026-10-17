import pytest
from flask import Flask
from common.response.response_code import ResponseCode
from plugin.codemig.codemig_task_manager.views import codemig_task_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(codemig_task_bp)  # 注册蓝图
    app.config['TESTING'] = True  # 启用测试模式
    return app.test_client()

# def test_create_and_process(client, mocker):
def create_and_process(client, mocker):
    mocker.patch(        'plugin.codemig.codemig_task_manager.codemig_task.create_task',        return_value=(True, (123, 321)))
    mocker.patch(        'plugin.codemig.codemig_task_manager.codemig_task.update_task_status',        return_value=(True))
    mocker.patch(        'plugin.codemig.codemig_task_manager.codemig_task.process_directory',        return_value=(True, None))

    # 模拟请求体数据
    request_data = {
        "user_name": "test_user",
        "task_name": "test_task",
        "upload_file_info_lists": [[1, 'file1']]
    }

    # 发送 POST 请求
    response = client.post('/task/create', json=request_data)
    assert response.json == {"code": 0, "msg": ResponseCode.OK, "task_id": 321}
