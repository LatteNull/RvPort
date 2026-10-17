import os
import json
import multiprocessing
import time
import urllib
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix


from bp import action_bp
from common.ai_key.ai_key_utils import load_ai_magic_values
from common.db.SQLOperation import DB_INFO
from framework.config_manager.config import SysConfig
from framework.log_manager.operation_log import OperationLog
from framework.plugin_manager.plugin_init import init_plugin
from front_service import static_bp
from framework.user_manager.user_db import UserManager


def init_db():
    UserManager.init_default_user()
    SysConfig.list_all()
    OperationLog.del_expire_log()


def list_routes(app):

    output = []
    for rule in app.url_map.iter_rules():
        options = {}
        for arg in rule.arguments:
            options[arg] = f"[{arg}]"

        methods = ','.join(rule.methods)
        url = urllib.parse.unquote(f"{rule}")
        line = f"{rule.endpoint:50s} {methods:20s} {url}"
        output.append(line)

    for line in sorted(output):
        print(line)


def init_background_process():
    """
    后台进程：保活子进程，供后续扩展后台任务使用。
    """

    def run_tasks():
        while True:
            time.sleep(3600)

    process = multiprocessing.Process(target=run_tasks)
    process.daemon = True
    process.start()


def init(test_config):
    init_db()
    init_plugin()
    if test_config is None:
        init_background_process()
        load_ai_magic_values()


def create_app(key, test_config=None):
    app_instance = Flask('master')
    app_instance.secret_key = key
    app_instance.wsgi_app = ProxyFix(app_instance.wsgi_app, x_for=1)

    if test_config is None:
        app_instance.config.from_file(os.path.join(os.path.dirname(__file__), "config.json"),
                                      load=json.load, silent=True)
    else:
        app_instance.config.from_mapping(test_config)
        if 'db_file' in test_config:
            DB_INFO.update_file(test_config['db_file'])
    init(test_config)

    # 注册蓝图
    app_instance.register_blueprint(action_bp)
    print("action_bp register_blueprint ok")

    if app_instance.config.get('DEBUG', False):
        app_instance.register_blueprint(static_bp)
        print("static_bp register_blueprint ok")
        print("============ list all routes: ============")
        list_routes(app_instance)
    else:
        app_instance.config.update(SESSION_COOKIE_SECURE=True,  # 仅通过HTTPS传输
                                   SESSION_COOKIE_HTTPONLY=True,  # 防止XSS访问
                                   SESSION_COOKIE_SAMESITE='Lax',  # CSRF保护)
                                   )

    return app_instance
