1.脚本运行测试
```pytest.sh```
2. vscode配置测试用例调试
在launch.json增加如下配置：
```aiignore
        {
            "name": "Python: pytest_server",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/kitvenv/bin/pytest",  // 或者根据你的环境调整路径
            "args": [
              "tests/server",
            ],
            "env": {
              "PYTHONPATH": "${workspaceFolder}/server"
            }

    }
```
3.用pycharm调试，则settings->project:performance_kit->Project Structure 选中 tests/server,然后mark as Tests

4.查看测试用例覆盖情况

a）pycharm，左侧树在测试用例比如tests/server/framework_test/user_manager/test_login.py（或者目录比如tests/server/framework_test/user_manager)上右键‘More Run/Debug'->Run xx with Coverage,会在源码标记，绿色是覆盖的，红色是未覆盖的

b）vscode需要正确配置测试框架（如 pytest、unittest 或 nose），以便显示 Run Tests 选项。

配置方法：

i. 在 VSCode 中打开命令面板（Ctrl+Shift+P），输入并选择 Python: Configure Tests。

ii. 选择你的测试框架（如 pytest）。

iii. 配置完后，VSCode 会自动检测测试文件，右键菜单会出现 Run Tests 选项。
```
pip install pytest-cov
```
然后在.vscode/settings.json写入以下内容
```
{
    "python.testing.pytestArgs": ["--cov=server", "--cov-report=term-missing", "tests/server"],
    "python.testing.unittestEnabled": false,
    "python.testing.pytestEnabled": true
}
```
然后ctrl+P，Tests:run all test with coverage,或者在tests/server上右键选Run Tests with Coverage

如果不好使，更新vscode版本
