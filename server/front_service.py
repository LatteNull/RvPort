import os.path

from flask import send_from_directory, Blueprint

static_bp = Blueprint('static', __name__, url_prefix='/')
print("static_bp init ok")


# 前端静态文件
@static_bp.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), filename)


# 首页
@static_bp.route('/')
def index_redirect():
    return serve_static('index.html')
