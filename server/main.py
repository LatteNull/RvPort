import sys
import json
import os
import secrets
import gunicorn.app.base

from app import create_app


def _resolve_session_key(config, config_path):
    """解析 Flask session 签名密钥，优先级：环境变量 CODEMIG_SECRET_KEY >
    config.json 的 key > 按模式兜底。

    - DEBUG（开发模式）：key 为空时自动生成随机密钥并写回 config.json，
      免去手工配置步骤；写回失败（只读目录等）则仅本次运行使用。
    - 生产模式：key 为空直接报错退出——静默用临时密钥会导致重启后所有
      用户 session 失效，显式失败优于隐性问题。
    """
    env_key = os.environ.get("CODEMIG_SECRET_KEY", "").strip()
    if env_key:
        return env_key

    key = (config.get("key") or "").strip()
    if key:
        return key

    generated = secrets.token_urlsafe(32)
    if config.get("DEBUG"):
        config["key"] = generated
        try:
            with open(config_path, "w") as config_file:
                json.dump(config, config_file, indent=2, ensure_ascii=False)
                config_file.write("\n")
            print("已自动生成会话密钥并写入 config.json（仅开发模式；"
                  "生产环境请显式配置 key 或 CODEMIG_SECRET_KEY）")
        except OSError as e:
            print(f"警告: 会话密钥写回 config.json 失败（{e}），本次运行使用临时密钥")
        return generated

    raise RuntimeError(
        "config.json 的 key（会话密钥）为空：生产模式要求显式配置。"
        "请执行 key=$(openssl rand -base64 32) 并写入 config.json 的 \"key\" 字段，"
        "或设置环境变量 CODEMIG_SECRET_KEY。"
    )


class StandaloneApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, application, args=None):
        self.options = args or {}
        self.application = application
        super().__init__()

    def load_config(self):
        config_map = {name: value for name, value in self.options.items()
                      if name in self.cfg.settings and value is not None}
        for name, value in config_map.items():
            self.cfg.set(name.lower(), value)

    def load(self):
        return self.application


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r") as config_file:
            config = json.load(config_file)
        ip = config.get("server_ip", "127.0.0.1")
        port = config.get("server_port", 8080)
        server_threads = config.get("server_threads", 4)
        key = _resolve_session_key(config, config_path)
        app = create_app(key)
        if config.get('DEBUG'):
            app.run(host=ip, port=port)
        else:
            options = {
                'bind': f'{ip}:{port}',
                'workers': 1,
                'threads': server_threads,
                'timeout': 120,
                'accesslog': '-',
                'errorlog': '-',
                'loglevel': 'info'
            }
            StandaloneApplication(app, options).run()
    except Exception as e:
        print('start app error:', e)
        sys.exit(1)
