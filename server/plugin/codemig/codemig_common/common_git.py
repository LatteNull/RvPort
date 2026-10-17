# 标准库导入
import os
import sys
from pathlib import Path

# 第三方库导入
from git import Repo
from git.exc import GitCommandError, GitError, InvalidGitRepositoryError
from gitdb.exc import ODBError

# 项目路径设置
MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

# 项目导入 - common 模块
from common.public import logger
from common.public.public import get_codemig_data_path

# 项目导入 - plugin.codemig 模块
from plugin.codemig.codemig_common.codemig_common_utils import query_file_path_from_database

LOGGER = logger.init_log('codemig')

# commit message 4 元组白名单（type / stage / src / reason）
# src 表示提交来源模块（前端组件或后端 agent）；reason 表示具体动作语义。
# v3.2 扩展：新增 "marker" type/stage 与 "codemig-boundary" src，
# 以及 9 个用户动作边界 reason。
COMMIT_TYPE_WHITELIST = {"manual", "ai", "project-manual", "marker"}
COMMIT_STAGE_WHITELIST = {"init", "before", "after", "start", "end", "marker"}
COMMIT_SRC_WHITELIST = {
    "codemig-file-change-view",
    "codemig-project-migrate-view",
    "codemig-agent",
    "codemig-init",
    "codemig-boundary",  # v3.2 新增：前端边界 commit 的 src
}
COMMIT_REASON_WHITELIST = {
    "user-save",
    "user-rollback",
    "user-edit-save",
    "agent-start",
    "agent-finish",
    "first-init",
    "agent-start-ut_test",
    "intermediate-user-stop",
    "intermediate-error",
    # ★ v3.2 新增 9 个边界 reason：
    "user-click-run-migrate",
    "user-click-run-ut_test",
    "user-click-resume-migrate",
    "user-click-resume-ut_test",
    "stage-end-success",
    "stage-end-error",
    "stage-end-cancel",
}

# commit message 严格匹配正则（首行），用于 _parse_commit_fields 与 _parse_commit_label。
# v3.2 扩展：type 与 stage 增加 marker / start / end 备选值。
COMMIT_MESSAGE_REGEX = (
    r"^Save type:(?P<type>manual|ai|project-manual|marker)\s+"
    r"stage:(?P<stage>init|before|after|start|end|marker)\s+"
    r"src:(?P<src>[a-z][a-z0-9-]+)\s+"
    r"reason:(?P<reason>[A-Za-z0-9_-]{1,64})$"
)

def get_repo_path(user_name, dir_id) -> Path:
    return Path(get_codemig_data_path()) / user_name / str(dir_id) / "changed"

def convert_abs_path_to_repo_path(user_name, dir_id, file_path:Path):
    """
    将绝对路径转换为 repo 内的相对路径
    """
    if not file_path.is_absolute():
        return False, "File path is not absolute."
    code_path = get_repo_path(user_name, dir_id)
    return True, Path(str(file_path).strip().replace(code_path.as_posix(), ""))


def commit_git_repo(user_name, dir_id, type, stage, src=None, reason=None, force=False):
    """
    提交 git 仓库。
    改造说明（v4.1）：
    - 引入 src + reason 两个新参数，明确 commit 来源与语义。
    - 老调用点（未传 src/reason）归一为 ("codemig-file-change-view", "unknown")，
      仅供存量路径平滑过渡；新代码必须显式传入白名单内的值。
    - commit message 格式升级为:
        "Save type:{type} stage:{stage} src:{src} reason:{reason}"

    改造说明（v3.2）：
    - 新增 force 参数，支持硬边界语义：
        - force=False（默认，向后兼容）：保留 is_dirty 守卫，干净工作区跳过 commit
        - force=True：跳过守卫，强制 commit（--allow-empty），
          即使工作区完全没改也会留一条 marker commit

    Args:
        user_name: 用户名
        dir_id: 目录ID
        type: 提交者类型，必须在 COMMIT_TYPE_WHITELIST 内
        stage: 阶段，必须在 COMMIT_STAGE_WHITELIST 内
        src: 提交来源模块，必须在 COMMIT_SRC_WHITELIST 内（默认兼容值）
        reason: 提交语义，必须在 COMMIT_REASON_WHITELIST 内（默认兼容值）
        force: 是否强制 commit（v3.2 新增），默认 False
    Returns:
        tuple: (status, git_hash, git_message, git_time)
            status: True 表示成功, False 表示失败
            git_hash: 提交哈希
            git_message: 提交消息
            git_time: 提交时间
    """
    # 白名单校验。
    # - src/reason 任一为 None：视为老调用点，归一为兼容值，不做白名单校验（向后兼容）。
    # - src/reason 都已显式传入：做强校验，不通过返回错误信息。
    src_is_legacy = (src is None) or (reason is None)
    if src_is_legacy:
        src = src or "codemig-file-change-view"
        reason = reason or "unknown"
    else:
        if type not in COMMIT_TYPE_WHITELIST:
            return False, f"commit_git_repo: type '{type}' not in whitelist"
        if stage not in COMMIT_STAGE_WHITELIST:
            return False, f"commit_git_repo: stage '{stage}' not in whitelist"
        if src not in COMMIT_SRC_WHITELIST:
            return False, f"commit_git_repo: src '{src}' not in whitelist"
        if reason not in COMMIT_REASON_WHITELIST:
            return False, f"commit_git_repo: reason '{reason}' not in whitelist"

    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return False, "Code path does not exist."

    # 检查是否是 git 仓库,如果不是,初始化一个
    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        repo = Repo.init(code_path)
        LOGGER.info(f"Initialized git repository at {code_path}")

    # v3.2：force 分流
    # - force=True：跳过 is_dirty 守卫，强制 commit（--allow-empty）
    # - force=False：保留原有 is_dirty 守卫
    need_commit = force or repo.is_dirty(untracked_files=True)
    if need_commit:
        repo.git.add(all=True)
        commit_message = f"Save type:{type} stage:{stage} src:{src} reason:{reason}"
        repo.git.config('user.name', user_name)
        repo.git.config('user.email', 'user_name@eco.com')
        if force:
            # 硬边界 commit：即使 working tree clean 也强制留痕
            repo.git.commit(m=commit_message, allow_empty=True)
            LOGGER.info(
                f"Force-committed (allow_empty) for {user_name} dir={dir_id} "
                f"reason={reason} force={force}"
            )
        else:
            repo.git.commit(message=commit_message)
            LOGGER.info(f"Committed current state to git repository at {code_path}")

    # 获取当前 HEAD 的提交信息
    try:
        git_hash = repo.head.commit.hexsha
        git_message = repo.head.commit.message.strip().split('\n')[0]  # 只取第一行
        git_time = repo.head.commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError) as e:
        # 如果没有提交,返回错误
        return False, f"No commits found in repository: {str(e)}"

    return True, (git_hash, git_message, git_time)

def generate_patch_from_initial_commit(user_name, dir_id):
    """
    使用 GitPython 生成从初始提交到当前 HEAD 的 patch 文件
    Args:
        user_name: 用户名
        dir_id: 目录ID
    Returns:
        tuple: (status, patch_content)
            status: True 表示成功, False 表示失败
            patch_content: 如果成功,返回 patch 内容字符串；如果失败,为错误信息字符串
    """
    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return False, "Code path does not exist."

    # 检查是否是 git 仓库
    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        return False, "Git repository not found. Please ensure the repository is initialized."
    try:
        # 获取所有提交
        commits = list(repo.iter_commits())
        if len(commits) == 0:
            return False, "No commits found in repository."

        # 找到初始提交（第一个提交,通常是 "Initial commit"）
        initial_commit = commits[-1]  # 最旧的提交
        current_commit = repo.head.commit  # 当前 HEAD

        # 如果只有一个提交,说明没有更改
        if initial_commit.hexsha == current_commit.hexsha:
            return True, ""

        # 使用 GitPython 生成 patch
        # 使用 git diff 命令生成统一的 diff 格式（unified diff format）
        # 生成标准的 unified diff 格式
        # --binary：二进制文件以 base85 编入补丁，git apply 可完整还原
        patch_content = repo.git.diff(
            initial_commit.hexsha,
            current_commit.hexsha,
            '--unified=3',  # 使用 3 行上下文
            '--binary',
        )

        if not patch_content or not patch_content.strip():
            return True, ""
        if not patch_content.endswith("\n"):
            patch_content = patch_content + "\n"

        # 添加 patch 头部信息
        header = (
            f"# Patch file generated from Git repository\n"
            f"# Initial commit: {initial_commit.hexsha[:8]} ({initial_commit.message.strip()})\n"
            f"# Current commit: {current_commit.hexsha[:8]} ({current_commit.message.strip()})\n"
            f"# Generated for user: {user_name}, dir_id: {dir_id}\n\n"
        )

        full_patch = header + patch_content
        LOGGER.info(f"Generated patch from {initial_commit.hexsha[:8]} to {current_commit.hexsha[:8]}")
        return True, full_patch

    except GitCommandError as e:
        error_msg = f"Git command error: {str(e)}"
        LOGGER.error(error_msg)
        return False, error_msg
    except (AttributeError, IndexError, TypeError, ValueError) as e:
        error_msg = f"Error generating patch: {str(e)}"
        LOGGER.error(error_msg, exc_info=True)
        return False, error_msg


def query_original_file_from_git(user_name, dir_id, file_id):
    """
    通过 git 获取文件初始版本的内容
    Args:
        user_name: 用户名
        dir_id: 目录ID
        file_id: 文件ID
    Returns:
        tuple: (status, file_content)
            status: True 表示成功, False 表示失败
            file_content: 如果成功,返回文件内容字符串；如果失败,为错误信息字符串
    """
    try:
        # 1) 查数据库拿到 file_path
        status, file_path = query_file_path_from_database(user_name, dir_id, file_id)
        if not status or not file_path:
            LOGGER.error("Failed to query file_path from database: %s", file_path)
            return False, ""

        status, rel_path = convert_abs_path_to_repo_path(user_name, dir_id, Path(file_path))
        if not status:
            LOGGER.error("Failed to convert file path to repo path: %s", file_path)
            return False, ""
        rel_path = str(rel_path).lstrip("/")

        # 2) 打开对应任务的 code 仓库
        code_path = get_repo_path(user_name, dir_id)
        if not code_path.exists():
            LOGGER.error("Code path does not exist: %s", code_path)
            return False, ""
        try:
            repo = Repo(code_path)
        except InvalidGitRepositoryError:
            LOGGER.error("Git repository not found at %s", code_path)
            return False, ""

        commits = list(repo.iter_commits())
        if not commits:
            LOGGER.error("No commits found in repository at %s", code_path)
            return False, ""

        # 4) 取初始提交中的文件内容
        try:
            initial_commit = commits[-1]  # 最旧的提交
            blob = initial_commit.tree / rel_path
            data = blob.data_stream.read()
        except KeyError:
            # TODO: 新增文件：初始提交中不存在,返回空串
            return True, ""

        # 优先 utf-8,失败则 replace
        try:
            return True, data.decode("utf-8")
        except UnicodeDecodeError:
            return True, data.decode("utf-8", errors="replace")

    except (OSError, AttributeError, ValueError) as e:
        LOGGER.error(
            "query original file from git failed: %s", str(e), exc_info=True)
        return False, ""


def query_new_files_from_git(user_name, dir_id):
    """
    通过 git 获取当前未跟踪的文件列表
    Args:
        user_name: 用户名
        dir_id: 目录ID
    Returns:
        tuple: (status, file_list)
            status: True 表示成功, False 表示失败
            file_list: 如果成功,返回未跟踪文件列表；如果失败,返回空列表[]
    """
    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        LOGGER.error("Code path does not exist: %s", code_path)
        return False, []

    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        repo = Repo.init(code_path)
        repo.git.config('user.name', user_name)
        repo.git.config('user.email', 'user_name@eco.com')
        LOGGER.warning("Git repository not found at %s, initialized new repository", code_path)
        return True, []

    try:
        # 获取未跟踪的文件列表
        untracked_files = []
        for file_path in repo.untracked_files:
            # 确保文件存在且是相对于仓库根目录的路径
            full_path = code_path / file_path
            if full_path.exists() and full_path.is_file():
                untracked_files.append(file_path)
        
        return True, untracked_files
    except (AttributeError, OSError, ValueError) as e:
        LOGGER.error("Error getting untracked files from git: %s", e, exc_info=True)
        return False, []


# 检查 commit message 是否是回滚版本
def _is_revert_commit(commit):
    """
    检查 commit message 是否是文件回滚提交
    回滚提交的特征：
    1. commit message 中包含 "revert"（不区分大小写）
    2. commit message 中包含 "last commit:"（表示回滚到的目标 commit)
    3. commit message 中包含 "from commit" 和 "to commit"（表示回滚操作）
    Args:
        commit: Git commit 对象
    Returns:
        tuple: (status, last_commit_hash)
            status: True 表示是回滚提交, False 表示不是
            last_commit_hash: 回滚到的目标的 last_commit_hash
    """
    if commit is None:
        return False, None
    msg = (commit.message or "").strip()
    if not msg:
        return False, None

    msg_lower = msg.lower()
    # 检查是否包含回滚关键词
    has_revert = "revert" in msg_lower
    has_last_commit = "last commit:" in msg_lower
    has_from_to = "from commit" in msg_lower and "to commit" in msg_lower

    # 回滚提交必须同时满足：包含 revert 和 last commit
    # 如果还包含 from commit/to commit，则更确定是回滚提交
    if has_revert and has_last_commit:
        last_commit_hash = msg.split("last commit:")[1].strip()
        return True, last_commit_hash

    # 如果只有 from commit/to commit，也可能是回滚（但这种情况较少）
    if has_from_to and has_last_commit:
        last_commit_hash = msg.split("last commit:")[1].strip()
        return True, last_commit_hash

    return False, None

def revert_to_last_commit(user_name, dir_id, file_path:Path):
    """
    将指定文件回滚到上一次提交的内容
    注意：会直接修改工作区的文件内容，不会提交到 git 仓库

    1. 找到该文件的当前commit A 的上一次commit B,并获取该commit B的该文件内容
    2. msg 记录:将文件从commit A 回滚到commit B, parent: commit B的hexsha
    3. 如果当前commit A 的 msg 是回滚的版本,继续回滚到commit B的上一次commit,直到找到一个不是回滚的版本

    Args:
        user_name: 用户名
        dir_id: 目录ID
        file_path: 文件路径(绝对路径Path 对象)
    Returns:
        tuple: (status, msg, content)
            status: True 表示成功, False 表示失败
            msg: 成功或错误信息
            content: 回滚后的文件内容（如果文件被删除则为空字符串）
    """
    file_content = ''
    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return False, "Code path does not exist.", file_content

    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        return False, "Git repository not found.", file_content

    # 将 file_path 转换为 repo 内的相对路径
    status, rel_path = convert_abs_path_to_repo_path(user_name, dir_id, file_path)
    if not status:
        return False, "Failed to convert file path to repo path.", file_content
    rel_path = str(rel_path).lstrip("/")

    # 查找包含该文件的目标 commit：
    # 1. 如果当前 commit 是回滚版本，根据 last hash 继续查找
    # 2. 如果当前 commit 不是回滚版本，直接找它的上一个
    target_commit = None       # 目标 commit
    last_commit_hash = None    # 目标 commit 的 真实上一个 commit 的 hash， 记录用于后续的回滚
    tmp_commit_hash = None     # 临时 commit 的 hash，用于判断是否是回滚版本
    dist_hash = None           # 目标 commit 的 hash，用于判断是否找到回滚版本
    to_this_commit = False     # 是否找到目标 commit
    for i, commit in enumerate(repo.iter_commits(paths=rel_path)):
        if target_commit is not None:
            if last_commit_hash is None:
                last_commit_hash = commit.hexsha
            break

        if to_this_commit:
            if dist_hash is not None and dist_hash != commit.hexsha:
                continue
            target_commit = commit
            status, tmp_commit_hash = _is_revert_commit(commit)
            if status:
                last_commit_hash = tmp_commit_hash
            continue

        status, tmp_commit_hash = _is_revert_commit(commit)
        if not status:
            to_this_commit = True
        else:
            if dist_hash is None:
                dist_hash = tmp_commit_hash

    if target_commit is None:
        return True, "没有可回退版本", file_content

    # 从目标 commit 中获取文件内容
    try:
        blob = target_commit.tree / rel_path
        data = blob.data_stream.read()
        file_content = data.decode("utf-8", errors="replace")
    except (KeyError, AttributeError, IOError) as e:
        LOGGER.error(f"Failed to read blob content for {rel_path}: {e}")
        return False, f"Failed to read file content from commit: {str(e)}", file_content

    # 将内容写回工作区文件
    target_file = code_path / rel_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
    except (OSError, IOError, FileNotFoundError, PermissionError) as e:
        LOGGER.error(f"Failed to write file {target_file}: {e}")
        return False, f"Failed to write file: {str(e)}", file_content

    try:
        # 构建返回消息
        current_hexsha = repo.head.commit.hexsha
        target_hexsha = target_commit.hexsha
        parent_info = f"last commit: {last_commit_hash}"
        msg = (
            f"revert file {rel_path} from commit {current_hexsha} to commit {target_hexsha} "
            f"{parent_info}"
        )

        if repo.is_dirty(untracked_files=True):
            repo.git.add(rel_path)
            repo.git.config('user.name', user_name)
            repo.git.config('user.email', 'user_name@eco.com')
            repo.git.commit(message=msg)
            LOGGER.info(f"Reverted file {rel_path} from {current_hexsha} to {target_hexsha}")
            return True, msg, file_content
    except GitCommandError as e:
        error_msg = f"Git command error: {str(e)}"
        LOGGER.error(error_msg)
        return False, error_msg, file_content

def restore_workspace(user_name, dir_id):
    """
    丢弃工作区的改动 删除未跟踪的文件
    Args:
        user_name: 用户名
        dir_id: 目录ID
    Returns:
        tuple: (status, msg)
            status: True 表示成功, False 表示失败
            msg: 成功或错误信息
    """
    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        LOGGER.error("Code path does not exist: %s", code_path)
        return False, "Code path does not exist."

    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        LOGGER.error("Git repository not found at %s", code_path)
        return False, "Git repository not found."

    try:
        repo.git.checkout('--', '.')  # 丢弃工作区改动
        repo.git.clean('-f', '-d')  # 删除未跟踪的文件和目录
        LOGGER.info(f"Restore repository {code_path.as_posix()} ")
        return True, ''
    except GitCommandError as e:
        LOGGER.error(f"Git command error while restoring workspace: {e}")
        return False, f"Git command error: {str(e)}"


def reset_to_commit(user_name, dir_id, target_hexsha):
    """
    将整个仓库硬回退到指定 commit（hard reset + clean）。
    用于一键迁移失败回滚 / 手动回退，与单文件的 revert_to_last_commit（逐文件软回滚）完全隔离。

    Args:
        user_name: 用户名
        dir_id: 目录ID
        target_hexsha: 目标 commit 的完整 hash

    Returns:
        tuple: (status, msg)
            status: True 表示成功, False 表示失败
            msg: 成功返回 target_hexsha, 失败返回错误信息
    """
    if not target_hexsha:
        return False, "Target commit hash is empty."

    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return False, "Code path does not exist."

    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        return False, "Git repository not found."

    try:
        repo.git.reset('--hard', target_hexsha)
        repo.git.clean('-f', '-d')
        LOGGER.info(f"Reset repo to {target_hexsha[:8]} for user={user_name} dir_id={dir_id}")
        return True, target_hexsha
    except GitCommandError as e:
        LOGGER.error(f"Git reset error: {e}")
        return False, f"Git command error: {str(e)}"


import re

def _parse_commit_fields(message):
    """用 COMMIT_MESSAGE_REGEX 解析 commit message；失败时返回 None。

    ★ v6.0.0-ROLLBACK-NONCE：保留对历史 commit '#nonce=<x>' 后缀的 strip。
       v5 阶段产生过带 nonce 后缀的 commit（前/后端共享同一个 nonce 后被去重机制跳过），
       这些 commit 仍可能留在某些用户的 git 历史里。如果不在解析前 strip nonce，
       COMMIT_MESSAGE_REGEX 的 reason 段 [A-Za-z0-9_-]{1,64}$ 会 NO MATCH，
       所有带 nonce 的历史 commit 都被降级成"提交点"。
       - v6 已停止生成带 nonce 的 commit（新 commit 永远不带 nonce）
       - 但解析时仍 strip 以兼容老 commit
       - reason 字段白名单里没有 '#' 字符，split('#', 1)[0] 安全

    Returns:
        dict | None: {type, stage, src, reason} 或 None
    """
    msg = (message or "").strip().split('\n')[0]
    if not msg:
        return None
    # strip 历史 nonce 后缀（v5 阶段产生的 commit 末尾可能有 '#nonce=<x>'）。
    # 新 commit（v6+）没有 nonce，split 后整段保留。
    msg = msg.split('#', 1)[0]
    m = re.match(COMMIT_MESSAGE_REGEX, msg)
    if not m:
        return None
    return m.groupdict()


def _parse_commit_label(message):
    """从 commit message 解析前端展示用标签。

    新格式严格匹配优先；老格式（"Save type:X stage:Y"）自动降级映射；
    完全无法识别时返回通用"提交点"。

    Returns:
        dict: {prefix, category, label}
            prefix: 用于历史下拉框前缀的中文短标签
            category: 类别标识（init/single-save/migrate-before/migrate-after/manual-save/other）
            label: 长标签（保留向后兼容，前端 label 字段）
    """
    fields = _parse_commit_fields(message)
    if fields:
        reason_v = fields.get('reason')
        type_v = fields.get('type')
        stage_v = fields.get('stage')

        # ★ v3.2 新增：用户动作边界 reason 渲染
        if reason_v == 'user-click-run-migrate':
            return {'prefix': '点击运行·代码生成', 'category': 'boundary-click-run', 'label': '[点击运行·代码生成]'}
        if reason_v == 'user-click-run-ut_test':
            return {'prefix': '点击运行·功能验证', 'category': 'boundary-click-run', 'label': '[点击运行·功能验证]'}
        # 性能优化阶段已下线：以下两个 mca_optimize 渲染分支仅为
        # 展示历史 commit 保留，新流程不再产生这两种 reason。
        if reason_v == 'user-click-run-mca_optimize':
            return {'prefix': '点击运行·性能优化', 'category': 'boundary-click-run', 'label': '[点击运行·性能优化]'}
        if reason_v == 'user-click-resume-migrate':
            return {'prefix': '点击继续·代码生成', 'category': 'boundary-click-resume', 'label': '[点击继续·代码生成]'}
        if reason_v == 'user-click-resume-ut_test':
            return {'prefix': '点击继续·功能验证', 'category': 'boundary-click-resume', 'label': '[点击继续·功能验证]'}
        if reason_v == 'user-click-resume-mca_optimize':
            return {'prefix': '点击继续·性能优化', 'category': 'boundary-click-resume', 'label': '[点击继续·性能优化]'}
        # ★ v6.0.0-UI-DISTINCT：stage-end-* 三 reason 按 src 区分
        #   src=codemig-boundary → 前端用户主动调 _postBoundaryCommit 留下的 marker
        #     （用户主动 stop / UI 标 success / UI 标 error）
        #   src=codemig-agent → 后端 generate_project_agent_response finally 块兜底
        #     （agent 正常 finish / GeneratorExit interrupted / 异常中断）
        #   历史上 v6 之前这三种情况都会留下 src=codemig-boundary 的前端 marker + src=codemig-agent 的
        #   后端 marker，git log 看就是 2 条同 reason 的 commit；下拉框只显示一个"阶段取消"让人困惑。
        #   现在按 src 区分后，前端 cancel 那条显示"用户取消"，后端 finally 那条显示"阶段取消"，
        #   用户能清楚看到"我点的取消 + 系统兜底的取消"两条独立 commit 链。
        src_v = fields.get('src')
        if reason_v == 'stage-end-success':
            if src_v == 'codemig-boundary':
                return {'prefix': '用户标记·完成', 'category': 'boundary-user-mark', 'label': '[用户标记·完成]'}
            return {'prefix': '阶段完成', 'category': 'boundary-stage-end', 'label': '[阶段完成]'}
        if reason_v == 'stage-end-error':
            if src_v == 'codemig-boundary':
                return {'prefix': '用户标记·失败', 'category': 'boundary-user-mark', 'label': '[用户标记·失败]'}
            return {'prefix': '阶段异常', 'category': 'boundary-stage-end', 'label': '[阶段异常]'}
        if reason_v == 'stage-end-cancel':
            if src_v == 'codemig-boundary':
                return {'prefix': '用户取消', 'category': 'boundary-user-cancel', 'label': '[用户取消]'}
            return {'prefix': '阶段取消', 'category': 'boundary-stage-end', 'label': '[阶段取消]'}

        # 兼容旧 reason
        if reason_v == 'intermediate-user-stop':
            return {'prefix': '中间态', 'category': 'migrate-intermediate', 'label': '中间态（可能不完整）'}
        if type_v == 'manual' and stage_v == 'init':
            return {'prefix': '初始版本', 'category': 'init', 'label': '初始版本'}
        if type_v == 'manual' and stage_v in ('before', 'after'):
            return {'prefix': '单文件保存', 'category': 'single-save', 'label': '单文件保存'}
        if type_v == 'ai' and stage_v == 'before':
            return {'prefix': '迁移前', 'category': 'migrate-before', 'label': '迁移前'}
        if type_v == 'ai' and stage_v == 'after':
            return {'prefix': '迁移后', 'category': 'migrate-after', 'label': '迁移后'}
        if type_v == 'project-manual' and stage_v in ('before', 'after'):
            return {'prefix': '手动保存', 'category': 'manual-save', 'label': '手动保存'}

    # 老格式兜底（仅看 type:X stage:Y 前缀，不依赖 src/reason）
    msg = (message or "").strip()
    if "type:ai" in msg and "stage:before" in msg:
        return {'prefix': '迁移前', 'category': 'migrate-before', 'label': '迁移前'}
    if "type:ai" in msg and "stage:after" in msg:
        return {'prefix': '迁移后', 'category': 'migrate-after', 'label': '迁移后'}
    if "type:manual" in msg and "stage:init" in msg:
        return {'prefix': '初始版本', 'category': 'init', 'label': '初始版本'}
    if msg:
        return {'prefix': '提交点', 'category': 'other', 'label': '保存点'}
    return {'prefix': '提交点', 'category': 'other', 'label': '提交点'}


def list_project_history(user_name, dir_id, max_count=50):
    """
    基于 git reflog 列出仓库所有历史快照点（保证 reset --hard 后仍可回跳）。
    reflog 记录 HEAD 的所有移动轨迹，即使某 commit 被 reset 丢弃，
    只要未被 gc 回收，仍可通过 newhexsha 重新指向。

    Args:
        user_name: 用户名
        dir_id: 目录ID
        max_count: 最多返回条数（reflog 时间倒序）

    Returns:
        tuple: (status, result)
            status: True 表示成功
            result: 历史点列表 [{hash, short_hash, label, prefix, category, time, message, is_current}]
            status: False 表示失败, result 为错误信息
    """
    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return False, "Code path does not exist."

    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        return False, "Git repository not found."
    except (GitError, OSError) as e:
        return False, f"Open git repository failed: {str(e)}"

    try:
        current_hash = repo.head.commit.hexsha
    except (ValueError, AttributeError) as e:
        return False, f"No commits found in repository: {str(e)}"

    try:
        # reflog: HEAD 的所有移动记录（最新在前）
        ref_entries = list(repo.head.log())
    except (GitError, ODBError) as e:
        LOGGER.error(f"Read reflog failed: {str(e)}")
        ref_entries = []

    def _build_entry(hexsha, message, time_str):
        meta = _parse_commit_label(message)
        return {
            'hash': hexsha,
            'short_hash': hexsha[:8],
            'label': meta.get('label', '提交点'),
            'prefix': meta.get('prefix', '提交点'),
            'category': meta.get('category', 'other'),
            'time': time_str,
            'message': message,
            'is_current': hexsha == current_hash,
        }

    seen = set()
    # ★ 修复：GitPython head.log() 按 reflog 文件顺序返回（最旧在前），与
    #   `git reflog` CLI（最新在前）相反。之前代码误以为"最新在前"直接原样
    #   append，导致返回顺序与本函数 docstring 承诺的"reflog 时间倒序"相反：
    #     1) 历史下拉框正序显示（最老在最上）；
    #     2) 前端 restoreFlowStatusFromHistory 假设新→旧、reverse 后按时间
    #        正序做 marker 配对——方向反掉后 stage-end-* 先于 user-click-run-*
    #        出现、配不上对，刷新页面后已完成阶段全部错误回退"就绪"。
    #   改为收集 (committed_datetime, entry) 后显式按提交时间倒序排序。
    entries_by_time = []
    for entry in ref_entries:
        hexsha = getattr(entry, 'newhexsha', '') or ''
        if not hexsha or hexsha in seen:
            continue
        seen.add(hexsha)
        try:
            commit = repo.commit(hexsha)
        except (GitError, ODBError, ValueError):
            continue
        message = (commit.message or "").strip().split('\n')[0]
        time_str = commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')
        entries_by_time.append((commit.committed_datetime, _build_entry(hexsha, message, time_str)))
    entries_by_time.sort(key=lambda t: t[0], reverse=True)
    # 截断放在排序后：取最新的 N 条（原实现按文件顺序截断会取到最老的 N 条）
    history = [entry for _, entry in entries_by_time[:max_count]]

    # 兜底：若 reflog 为空（旧仓库），退化为遍历 iter_commits
    if not history:
        try:
            for commit in repo.iter_commits(max_count=max_count):
                hexsha = commit.hexsha
                if hexsha in seen:
                    continue
                seen.add(hexsha)
                message = (commit.message or "").strip().split('\n')[0]
                time_str = commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')
                history.append(_build_entry(hexsha, message, time_str))
        except (GitError, ODBError, ValueError) as e:
            LOGGER.error(f"Iterate commits failed: {str(e)}")

    LOGGER.info(f"Listed {len(history)} history points for user={user_name} dir_id={dir_id}")
    return True, history


def generate_patch_between(user_name, dir_id, from_hash, to_hash=None):
    """
    生成两个 commit 之间的增量 patch。
    用于一键迁移的增量补丁导出，与单文件迁移（generate_patch_from_initial_commit 全量导出）完全隔离。

    Args:
        user_name: 用户名
        dir_id: 目录ID
        from_hash: 起点 commit hash
        to_hash: 终点 commit hash，None 表示当前 HEAD

    Returns:
        tuple: (status, result)
            status: True 表示成功
            result: patch 字符串（可能为空字符串）
            status: False 表示失败, result 为错误信息
    """
    if not from_hash:
        return False, "from_hash is empty."

    code_path = get_repo_path(user_name, dir_id)
    if not code_path.exists():
        return False, "Code path does not exist."

    try:
        repo = Repo(code_path)
    except InvalidGitRepositoryError:
        return False, "Git repository not found."
    except (GitError, OSError) as e:
        return False, f"Open git repository failed: {str(e)}"

    try:
        if to_hash is None:
            to_hash = repo.head.commit.hexsha

        # 起点终点相同：无变更
        if from_hash == to_hash:
            return True, ""

        patch_content = repo.git.diff(
            from_hash,
            to_hash,
            '--unified=3',
            '--binary',
        )
        if not patch_content or not patch_content.strip():
            return True, ""
        if not patch_content.endswith("\n"):
            patch_content = patch_content + "\n"

        try:
            from_msg = (repo.commit(from_hash).message or "").strip().split('\n')[0]
            to_msg = (repo.commit(to_hash).message or "").strip().split('\n')[0]
        except (GitError, ODBError):
            from_msg, to_msg = "", ""

        header = (
            f"# Incremental patch generated from Git repository\n"
            f"# From: {from_hash[:8]} ({from_msg})\n"
            f"# To:   {to_hash[:8]} ({to_msg})\n"
            f"# Generated for user: {user_name}, dir_id: {dir_id}\n\n"
        )
        full_patch = header + patch_content
        LOGGER.info(f"Generated incremental patch from {from_hash[:8]} to {to_hash[:8]}")
        return True, full_patch

    except GitCommandError as e:
        error_msg = f"Git command error: {str(e)}"
        LOGGER.error(error_msg)
        return False, error_msg
    except (AttributeError, IndexError, TypeError, ValueError) as e:
        error_msg = f"Error generating patch: {str(e)}"
        LOGGER.error(error_msg, exc_info=True)
        return False, error_msg