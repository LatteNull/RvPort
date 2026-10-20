# RvPort

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

RvPort migrates x86 / ARM projects to RISC-V: it scans source code, makefiles, and dependencies for architecture-specific migration points, generates fix suggestions from a built-in rule base, and optionally applies intelligent rewrites powered by LLMs.

## Features

- **Migration-point scanning**: C/C++ (makefile rules, intrinsics, builtins, architecture macros, inline assembly), Java (JNI, architecture-specific dependencies), Python (C extensions, ctypes/cffi), Go (cgo, unsafe/syscall), Rust (inline assembly, architecture-specific crates)
- **Fix suggestions**: per-point remediation guidance from the built-in rule base (x86 / AArch64 source architecture → RISC-V target architecture)
- **AI-powered rewriting**: once a self-hosted LLM gateway is configured, generate smarter rewrite suggestions for individual findings or entire files; Agent mode applies code changes automatically inside a container and produces patches
- **Dependency assessment**: architecture-compatibility scanning for Python / Go packages

## Requirements

| Item | Requirement |
| --- | --- |
| OS | CentOS/RHEL/openEuler / Ubuntu/Debian |
| Python | 3.13 |
| Node.js | >= 20 |
| Docker | >= 18.09 |

## Deployment Guide

```bash
# 1. Install system dependencies (example for Ubuntu/Debian)
sudo apt install -y gcc make patchelf zlib1g-dev libffi-dev libssl-dev libbz2-dev \
    libgdbm-dev uuid-dev libsqlite3-dev sqlcipher libsqlcipher-dev git

# CentOS/openEuler equivalent:
# yum install -y gcc make patchelf zlib-devel libffi-devel \
#   openssl-devel bzip2-devel gdbm-devel libuuid-devel sqlite-devel sqlcipher-devel

# 2. Install Python packages
pip install -r requirements-dev.txt

# 3. Initialize the database
python scripts/install_db.py
# For MySQL: set DB_TYPE to "mysql" in server/config.json, add the connection
# entries (MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_DATABASE), then initialize
# with the password:
echo -n '<password>' | python scripts/install_db.py db_type=mysql \
    mysql_host=127.0.0.1 mysql_port=3306 mysql_user=root mysql_database=codemig

# 4. Build the frontend
cd frontend
npm install --legacy-peer-deps
npm run build
mkdir -p ../server/static && cp -rf dist/frontend/browser/* ../server/static/
```

## Getting Started

The backend entry point is `server/main.py` (run it from the `server` directory so that `config.json` can be located):

```bash
cd server
python main.py
```

- `DEBUG: true` in `config.json` starts the Flask development server (for debugging); `false` starts gunicorn (1 worker, multi-threaded, for production)
- Session secret (the `key` field in `config.json`): auto-generated on first launch in development mode; production mode requires an explicit value (startup fails with specific instructions if unset), or inject one via the `CODEMIG_SECRET_KEY` environment variable
- Visit `http://<server_ip>:8080/` in a browser (for production, set `server_ip` in `config.json` to `0.0.0.0`)
- On first launch an administrator account **Admin** is created automatically (initial password `Codemig@123`); a forced password change on first login immediately invalidates the initial password

## AI Configuration

AI features require an API key configured by the administrator. Log in as admin → "API Key Management":

| Field | Example |
| --- | --- |
| Base URL | `https://your-llm-gateway.example.com/v1` |
| API Key | `sk-xxxxx...` |
| Model name | `Qwen3-235B-A22B` / `DeepSeek-V3` / `Kimi-K2-Instruct`, etc. |

If not configured, inference requests fail with an error that directs you to the configuration page.

### Agent Mode

Agent mode executes code-migration skills (migrate / uttest / asmrepair) inside Docker containers. Prepare the image first:

```bash
cd server/assets/ai-agent
./build_docker.sh x86        # or arm; produces codemig-agent-base_1.0.0_x86.tar
docker load -i codemig-agent-base_1.0.0_x86.tar
```

The account running the backend needs Docker access (`sudo usermod -aG docker $USER`, then re-login).

## Testing

```bash
cd tests/server
python -m pytest -q
```

## FAQ

**A migration task fails and the backend log shows `permission denied ... /var/run/docker.sock`**

The backend process lacks docker group membership (required by Agent mode). To fix:

1. `sudo usermod -aG docker $USER` (skip if already in the docker group; verify with `id | grep docker`)
2. **Log out and reconnect** — group membership only takes effect for new sessions
3. Restart the backend from the new session (the old process inherited group membership from the old session and must be restarted to pick it up)

Verify with: `docker ps` should succeed.

## Project Layout

```
├── server/               # Backend (Flask)
│   ├── framework/        #   Framework: users, config, logging, plugin management
│   ├── common/           #   Common: crypto, database, logging
│   ├── plugin/codemig/   #   Migration plugin (scanning, suggestions, AI, task management)
│   ├── assets/ai-agent/  #   Agent container image build scripts and skill assets
│   └── static/           #   Frontend build output (generated at build time)
├── frontend/             # Frontend (Angular)
├── scripts/              # Installation and utility scripts
├── data/                 # Runtime data (gitignored): databases, key files
└── tests/                # pytest test suite
```

## License

This project is open-sourced under the [Apache License 2.0](LICENSE).
