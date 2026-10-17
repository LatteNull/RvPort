#!/usr/bin/env python3
"""
自动扫描已安装的 Python 包和前端 Node 包（含传递依赖，排除开发工具），
提取完整 license 文本，生成开源组件声明 HTML 页面。

用法:
    python scripts/gen_license_html.py
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
OUT_HTML = FRONTEND / "src" / "assets" / "open-source-licenses.html"

# --- 开发/测试工具排除列表 -------------------------------------------------
# 这些包不随产品分发，仅用于开发/测试/打包环境
PY_DEV_PACKAGES = {
    "pytest", "pytest-asyncio", "pytest-mock", "pytest-cov",
    "coverage", "iniconfig", "pluggy", "pip", "setuptools", "wheel",
    "appdirs",  # 仅 setuptools 间接引用，非运行时
}

# --- 第三方基础运行时组件 ---------------------------------------------------
# 这些组件不通过 pip/npm 安装，而是随仓库分发
# 信息为人工维护，包含版本、主页、版权、许可证类型及全文
THIRD_PARTY_COMPONENTS = [
    {
        "name": "Python",
        "version": "3.13.0",
        "home": "https://www.python.org/",
        "author": "Python Software Foundation",
        "license_name": "PSF License Version 2 + Zero-Clause BSD (dual license)",
        "license_text": """Python 3.13 采用双许可: PSF License Version 2 和 Zero-Clause BSD (0BSD)。

PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2
--------------------------------------------

1. This LICENSE AGREEMENT is between the Python Software Foundation
("PSF"), and the Individual or Organization ("Licensee") accessing and
otherwise using this software ("Python") in source or binary form and
its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works,
distribute, and otherwise use Python alone or in any derivative version,
provided, however, that PSF's License Agreement and PSF's notice of copyright,
i.e., "Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved"
are retained in Python alone or in any derivative version prepared by Licensee.

3. In the event Licensee prepares a derivative work that is based on
or incorporates Python or any part thereof, and wants to make
the derivative work available to others as provided herein, then
Licensee hereby agrees to include in any such work a brief summary of
the changes made to Python.

4. PSF is making Python available to Licensee on an "AS IS"
basis.  PSF MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PSF MAKES NO AND
DISCLAIMS ANY REPRESENTATION OR WARRANTY OF MERCHANTABILITY OR FITNESS
FOR ANY PARTICULAR PURPOSE OR THAT THE USE OF PYTHON WILL NOT
INFRINGE ANY THIRD PARTY RIGHTS.

5. PSF SHALL NOT BE LIABLE TO LICENSEE OR ANY OTHER USERS OF PYTHON
FOR ANY INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES OR LOSS AS
A RESULT OF MODIFYING, DISTRIBUTING, OR OTHERWISE USING PYTHON,
OR ANY DERIVATIVE THEREOF, EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

6. This License Agreement will automatically terminate upon a material
breach of its terms and conditions.

7. Nothing in this License Agreement shall be deemed to create any
relationship of agency, partnership, or joint venture between PSF and
Licensee.  This License Agreement does not grant permission to use PSF
trademarks or trade name in a trademark sense to endorse or promote
products or services of Licensee, or any third party.

8. By copying, installing or otherwise using Python, Licensee
agrees to be bound by the terms and conditions of this License
Agreement.

License reference: https://docs.python.org/3/license.html""",
    },
    {
        "name": "Node.js",
        "version": "22.9.0, 26.4.0",
        "home": "https://nodejs.org/",
        "author": "OpenJS Foundation",
        "license_name": "MIT (Node.js core) + third-party licenses",
        "license_text": """Node.js 核心代码采用 MIT 许可证:

Copyright Node.js contributors. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

注意: Node.js 二进制内置了大量第三方组件 (deps/), 各自有独立许可证,
包括但不限于 OpenSSL (Apache 2.0)、V8 (BSD-3-Clause)、ICU (Unicode License v3)、
npm (Artistic License 2.0)、zlib (zlib License) 等。
完整许可证清单请参阅 Node.js 官方 LICENSE 文件。

License reference: https://github.com/nodejs/node/raw/HEAD/LICENSE""",
    },

]


def get_master_version():
    """从 server/version.py 读取主版本号"""
    version_file = ROOT / "server" / "version.py"
    try:
        text = version_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("VERSION"):
                return line.split("=", 1)[1].strip().strip("'\"")
    except Exception:
        pass
    return ""


def get_third_party_libs():
    """返回第三方基础运行时组件列表"""
    return list(THIRD_PARTY_COMPONENTS)


# Python 包分类：迁移工具的后端依赖（本包只含迁移工具，无性能工具）
MIGRATION_PY = {
    # 源码分析
    "tree-sitter", "tree-sitter-python", "tree-sitter-rust",
    "tree-sitter-go", "GitPython", "pyahocorasick", "tomlkit",
    "chardet", "openpyxl",
    # 运行环境
    "pymysql", "portalocker", "typing_extensions", "gunicorn",
    "APScheduler", "tzlocal", "treelib", "python-magic", "six",
    # 后端基础框架
    "Flask", "Werkzeug", "Jinja2", "itsdangerous", "blinker",
    "MarkupSafe", "SQLAlchemy", "sqlcipher3",
    "cryptography",
    "requests", "packaging",
    "charset-normalizer", "certifi", "idna", "urllib3",
}

# --- 常见标准协议全文 -------------------------------------------------------
STANDARD_LICENSES = {
    "MIT": """MIT License

Copyright (c) [year] [copyright holders]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Reference: https://opensource.org/licenses/MIT""",

    "0BSD": """BSD Zero Clause License

Copyright (c) [year] [author]

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.

Reference: https://opensource.org/licenses/0BSD""",

    "Public Domain": """This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this
software, either in source code form or as a compiled binary, for any purpose,
commercial or non-commercial, and by any means.

For more information, please refer to <http://unlicense.org>

Reference: https://unlicense.org""",

    "BSD-3-Clause": """BSD 3-Clause License

Copyright (c) [year], [copyright holder]

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Reference: https://opensource.org/licenses/BSD-3-Clause""",

    "BSD-2-Clause": """BSD 2-Clause License

Copyright (c) [year], [copyright holder]

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Reference: https://opensource.org/licenses/BSD-2-Clause""",

    "ISC": """ISC License

Copyright (c) [year] [copyright holder]

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.

Reference: https://opensource.org/licenses/ISC""",

    "Apache-2.0": """Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

   "License" shall mean the terms and conditions for use, reproduction,
   and distribution as defined by Sections 1 through 9 of this document.

   "Licensor" shall mean the copyright owner or entity authorized by
   the copyright owner that is granting the License.

   "Legal Entity" shall mean the union of the acting entity and all
   other entities that control, are controlled by, or are under common
   control with that entity. For the purposes of this definition,
   "control" means (i) the power, direct or indirect, to cause the
   direction or management of such entity, whether by contract or
   otherwise, or (ii) ownership of fifty percent (50%) or more of the
   outstanding shares, or (iii) beneficial ownership of such entity.

   "You" (or "Your") shall mean an individual or Legal Entity
   exercising permissions granted by this License.

   "Source" form shall mean the preferred form for making modifications,
   including but not limited to software source code, documentation
   source, and configuration files.

   "Object" form shall mean any form resulting from mechanical
   transformation or translation of a Source form, including but
   not limited to compiled object code, generated documentation,
   and conversions to other media types.

   "Work" shall mean the work of authorship, whether in Source or
   Object form, made available under the License, as indicated by a
   copyright notice that is included in or attached to the work
   (an example is provided in the Appendix below).

   "Derivative Works" shall mean any work, whether in Source or Object
   form, that is based on (or derived from) the Work and for which the
   editorial revisions, annotations, elaborations, or other modifications
   represent, as a whole, an original work of authorship. For the purposes
   of this License, Derivative Works shall not include works that remain
   separable from, or merely link (or bind by name) to the interfaces of,
   the Work and Derivative Works thereof.

   "Contribution" shall mean any work of authorship, including
   the original version of the Work and any modifications or additions
   to that Work or Derivative Works thereof, that is intentionally
   submitted to Licensor for inclusion in the Work by the copyright owner
   or by an individual or Legal Entity authorized to submit on behalf of
   the copyright owner. For the purposes of this definition, "submitted"
   means any form of electronic, verbal, or written communication sent
   to the Licensor or its representatives, including but not limited to
   communication on electronic mailing lists, source code control systems,
   and issue tracking systems that are managed by, or on behalf of, the
   Licensor for the purpose of discussing and improving the Work, but
   excluding communication that is conspicuously marked or otherwise
   designated in writing by the copyright owner as "Not a Contribution."

   "Contributor" shall mean Licensor and any individual or Legal Entity
   on behalf of whom a Contribution has been received by Licensor and
   subsequently incorporated within the Work.

2. Grant of Copyright License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   copyright license to reproduce, prepare Derivative Works of,
   publicly display, publicly perform, sublicense, and distribute the
   Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   (except as stated in this section) patent license to make, have made,
   use, offer to sell, sell, import, and otherwise transfer the Work,
   where such license applies only to those patent claims licensable
   by such Contributor that are necessarily infringed by their
   Contribution(s) alone or by combination of their Contribution(s)
   with the Work to which such Contribution(s) was submitted. If You
   institute patent litigation against any entity (including a
   cross-claim or counterclaim in a lawsuit) alleging that the Work
   or a Contribution incorporated within the Work constitutes direct
   or contributory patent infringement, then any patent licenses
   granted to You under this License for that Work shall terminate
   as of the date such litigation is filed.

4. Redistribution. You may reproduce and distribute copies of the
   Work or Derivative Works thereof in any medium, with or without
   modifications, and in Source or Object form, provided that You
   meet the following conditions:

   (a) You must give any other recipients of the Work or
       Derivative Works a copy of this License; and

   (b) You must cause any modified files to carry prominent notices
       stating that You changed the files; and

   (c) You must retain, in the Source form of any Derivative Works
       that You distribute, all copyright, patent, trademark, and
       attribution notices from the Source form of the Work,
       excluding those notices that do not pertain to any part of
       the Derivative Works; and

   (d) If the Work includes a "NOTICE" text file as part of its
       distribution, then any Derivative Works that You distribute must
       include a readable copy of the attribution notices contained
       within such NOTICE file, excluding those notices that do not
       pertain to any part of the Derivative Works, in at least one
       of the following places: within a NOTICE text file distributed
       as part of the Derivative Works; within the Source form or
       documentation, if provided along with the Derivative Works; or,
       within a display generated by the Derivative Works, if and
       wherever such third-party notices normally appear. The contents
       of the NOTICE file are for informational purposes only and
       do not modify the License. You may add Your own attribution
       notices within Derivative Works that You distribute, alongside
       or as an addendum to the NOTICE text from the Work, provided
       that such additional attribution notices cannot be construed
       as modifying the License.

   You may add Your own copyright statement to Your modifications and
   may provide additional or different license terms and conditions
   for use, reproduction, or distribution of Your modifications, or
   for any such Derivative Works as a whole, provided Your use,
   reproduction, and distribution of the Work otherwise complies with
   the conditions stated in this License.

5. Submission of Contributions. Unless You explicitly state otherwise,
   any Contribution intentionally submitted for inclusion in the Work
   by You to the Licensor shall be under the terms and conditions of
   this License, without any additional terms or conditions.
   Notwithstanding the above, nothing herein shall supersede or modify
   the terms of any separate license agreement you may have executed
   with Licensor regarding such Contributions.

6. Trademarks. This License does not grant permission to use the trade
   names, trademarks, service marks, or product names of the Licensor,
   except as required for reasonable and customary use in describing the
   origin of the Work and reproducing the content of the NOTICE file.

7. Disclaimer of Warranty. Unless required by applicable law or
   agreed to in writing, Licensor provides the Work (and each
   Contributor provides its Contributions) on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
   implied, including, without limitation, any warranties or conditions
   of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
   PARTICULAR PURPOSE. You are solely responsible for determining the
   appropriateness of using or redistributing the Work and assume any
   risks associated with Your exercise of permissions under this License.

8. Limitation of Liability. In no event and under no legal theory,
   whether in tort (including negligence), contract, or otherwise,
   unless required by applicable law (such as deliberate and grossly
   negligent acts) or agreed to in writing, shall any Contributor be
   liable to You for damages, including any direct, indirect, special,
   incidental, or consequential damages of any character arising as a
   result of this License or out of the use or inability to use the
   Work (including but not limited to damages for loss of goodwill,
   work stoppage, computer failure or malfunction, or any and all
   other commercial damages or losses), even if such Contributor
   has been advised of the possibility of such damages.

9. Accepting Warranty or Additional Liability. While redistributing
   the Work or Derivative Works thereof, You may choose to offer,
   and charge a fee for, acceptance of support, warranty, indemnity,
   or other liability obligations and/or rights consistent with this
   License. However, in accepting such obligations, You may act only
   on Your own behalf and on Your sole responsibility, not on behalf
   of any other Contributor, and only if You agree to indemnify,
   defend, and hold each Contributor harmless for any liability
   incurred by, or claims asserted against, such Contributor by reason
   of your accepting any such warranty or additional liability.

END OF TERMS AND CONDITIONS

APPENDIX: How to apply the Apache License to your work.

   To apply the Apache License to your work, attach the following
   boilerplate notice, with the fields enclosed by brackets "[]"
   replaced with your own identifying information. (Don't include
   the brackets!)  The text should be enclosed in the appropriate
   comment syntax for the file format. We also recommend that a
   file or class name and description of purpose be included on the
   same "printed page" as the copyright notice for easier
   identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

Reference: https://www.apache.org/licenses/LICENSE-2.0""",
}

LICENSE_FILE_PATTERNS = [
    "license", "license.md", "license.txt", "license-mit", "copying",
    "copying.txt", "notice", "unlicense", "copyright",
]


def get_standard_license(license_short):
    if not license_short:
        return None
    key = license_short.strip()
    if key in STANDARD_LICENSES:
        return STANDARD_LICENSES[key]
    key_upper = key.upper()
    for name, text in STANDARD_LICENSES.items():
        if name.upper() in key_upper:
            return text
    return None


def clean_url(url):
    if not url:
        return ""
    if "," in url and not url.startswith("http"):
        url = url.split(",", 1)[-1].strip()
    if url.upper() == "UNKNOWN":
        return ""
    if url.startswith("git+"):
        url = url[4:]
    if url.startswith("git://"):
        url = "https://" + url[6:]
    if url.endswith(".git"):
        url = url[:-4]
    return url


def is_dev_package(meta):
    """判断 Python 包是否是开发/测试工具"""
    name = meta.get("Name", "")
    if name.lower() in PY_DEV_PACKAGES:
        return True
    classifiers = meta.get_all("Classifier") or []
    for c in classifiers:
        if c.startswith("Framework ::") and (
            "Testing" in c or "Development" in c
        ):
            return True
    return False


# --- Python 包提取 ---------------------------------------------------------
def find_license_file_in_distinfo(distinfo_dir):
    candidates = []
    for item in sorted(distinfo_dir.rglob("*")):
        name_lower = item.name.lower()
        if item.is_file() and any(
            pat in name_lower for pat in LICENSE_FILE_PATTERNS
        ):
            candidates.append(item)
    for c in candidates:
        if c.name.lower() in ("license", "license.txt", "license.md",
                               "copying", "copying.txt"):
            return c
    return candidates[0] if candidates else None


def get_python_info(pkg_name):
    info = {
        "name": pkg_name, "version": "", "home": "",
        "author": "", "license_name": "", "license_text": "",
    }
    try:
        import importlib.metadata as md
        dist = md.distribution(pkg_name)
        meta = md.metadata(pkg_name)
        info["version"] = meta.get("Version", "")
        info["author"] = meta.get("Author-Email", "") or meta.get("Author", "")

        home = ""
        urls = meta.get_all("Project-URL") or []
        for u in urls:
            for kw in ("homepage", "repository", "source"):
                if kw in u.lower():
                    val = u.split(",", 1)[-1].strip()
                    if val.startswith("http"):
                        home = val
                        break
            if home:
                break
        if not home:
            home = meta.get("Home-page", "") or ""
        info["home"] = clean_url(home)

        lic_name = (meta.get("License-Expression") or meta.get("License") or "")
        if not lic_name or "UNKNOWN" in lic_name.upper() or len(lic_name) > 500:
            classifiers = meta.get_all("Classifier") or []
            lic_cls = [c for c in classifiers
                       if c.startswith("License ::")]
            if lic_cls:
                lic_name = lic_cls[-1].split("::")[-1].strip()
        info["license_name"] = (
            lic_name if lic_name and "UNKNOWN" not in lic_name.upper() else ""
        )

        distinfo_dir = Path(dist._path)
        lic_file = find_license_file_in_distinfo(distinfo_dir)
        if lic_file:
            try:
                text = lic_file.read_text(encoding="utf-8", errors="ignore")
                info["license_text"] = text.strip()
            except Exception:
                pass
        if not info["license_text"]:
            std = get_standard_license(info["license_name"])
            info["license_text"] = (
                std if std else (info["license_name"] or "UNKNOWN")
            )
    except Exception as e:
        info["license_text"] = f"(提取失败: {e})"
    return info


def scan_all_python():
    """自动扫描所有已安装的 Python 运行时包，排除开发工具"""
    import importlib.metadata as md
    results = []
    for dist in md.distributions():
        meta = md.metadata(dist.metadata["Name"])
        if meta and not is_dev_package(meta):
            info = get_python_info(dist.metadata["Name"])
            results.append(info)
    return results


# --- Node 包提取 -----------------------------------------------------------
def get_node_info(pkg_name, lockfile_key, pkg_meta):
    """从 package.json 元数据提取信息。lockfile_key 是 package-lock.json 中的完整路径"""
    info = {
        "name": pkg_name, "version": "", "home": "",
        "author": "", "license_name": "", "license_text": "",
    }
    pkg_dir = FRONTEND / lockfile_key
    if not pkg_dir.is_dir():
        pkg_dir = FRONTEND / "node_modules" / pkg_name
    pkg_json = pkg_dir / "package.json"
    d = pkg_meta
    if pkg_json.exists():
        try:
            d = json.loads(pkg_json.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        info["version"] = d.get("version", "")
        author = d.get("author", "")
        if isinstance(author, dict):
            author = author.get("name", "")
        info["author"] = author
        home = d.get("homepage", "") or ""
        if not home:
            repo = d.get("repository", "")
            if isinstance(repo, dict):
                repo = repo.get("url", "")
            home = repo
        info["home"] = clean_url(home)

        lic = d.get("license", "")
        if isinstance(lic, dict):
            lic = lic.get("type", "")
        info["license_name"] = lic or "UNKNOWN"
        lic_short = lic or "UNKNOWN"

        license_text = ""
        if pkg_dir.exists():
            all_files = sorted(pkg_dir.iterdir())
            for f in all_files:
                name_lower = f.name.lower()
                if f.is_file() and any(
                    pat in name_lower for pat in LICENSE_FILE_PATTERNS
                ):
                    try:
                        license_text = f.read_text(
                            encoding="utf-8", errors="ignore").strip()
                        break
                    except Exception:
                        pass
            if not license_text:
                tpn = pkg_dir / "ThirdPartyNotices.txt"
                if tpn.exists():
                    license_text = tpn.read_text(
                        encoding="utf-8", errors="ignore").strip()
        if license_text:
            info["license_text"] = license_text
        else:
            std = get_standard_license(lic_short)
            info["license_text"] = std if std else lic_short
    except Exception as e:
        info["license_text"] = f"(提取失败: {e})"
    return info


def scan_all_node():
    """从 package-lock.json 扫描所有非 dev 的 Node 包"""
    lockfile = FRONTEND / "package-lock.json"
    if not lockfile.exists():
        print("  (package-lock.json 不存在，跳过前端)")
        return []
    d = json.loads(lockfile.read_text(encoding="utf-8"))
    packages = d.get("packages", {})
    results = []
    for key, meta in packages.items():
        # 跳过根项目 (key 为空) 和 dev 依赖
        if not key or meta.get("dev"):
            continue
        pkg_name = key.replace("node_modules/", "")
        # 跳过嵌套路径如 node_modules/@scope/pkg/node_modules/xxx
        if "node_modules/" in pkg_name:
            pkg_name = pkg_name.rsplit("node_modules/", 1)[-1]
        # 避免重复
        if any(r["name"] == pkg_name for r in results):
            continue
        info = get_node_info(pkg_name, key, meta)
        info["name"] = pkg_name
        results.append(info)
    return results


# --- 分类与收集 -------------------------------------------------------------
def classify_python_packages(all_py):
    """筛出迁移工具用到的 Python 包（已安装环境中可能混有无关包）"""
    def norm(s):
        return s.lower().replace("-", "_").replace("_", "-")

    mig_names = {norm(n) for n in MIGRATION_PY}
    return [info for info in all_py if norm(info["name"]) in mig_names]


# --- HTML 生成 --------------------------------------------------------------
def esc(s):
    return html.escape(str(s)) if s else ""


def render_section(title, libs):
    parts = [f'<h2 class="section-title">{esc(title)}</h2>']
    for lib in sorted(libs, key=lambda l: l["name"].lower()):
        parts.append('<div class="lib-entry">')
        parts.append(
            f'<div class="lib-name">{esc(lib["name"])} '
            f'<span class="lib-version">v{esc(lib["version"])}</span></div>'
        )
        if lib.get("home"):
            parts.append(
                f'<div class="lib-home">'
                f'<a href="{esc(lib["home"])}" target="_blank" rel="noopener">'
                f'{esc(lib["home"])}</a></div>'
            )
        if lib.get("author"):
            parts.append(
                f'<div class="lib-copy">Copyright (c) {esc(lib["author"])}</div>'
            )
        if lib.get("license_name"):
            parts.append(
                f'<div class="lib-license-name">'
                f'License: {esc(lib["license_name"])}</div>'
            )
        parts.append(
            f'<pre class="lib-license-text">{esc(lib["license_text"])}</pre>'
        )
        parts.append('</div>')
    return "\n".join(parts)


def generate_html(third_party_libs, migration_libs, node_libs):
    css = """
    * { box-sizing: border-box; }
    body {
        font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue",
                     Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
        margin: 0; padding: 0; background: #f5f7fa; color: #333;
        line-height: 1.6;
    }
    .header {
        background: #2C89E6; color: #fff; padding: 28px 40px;
    }
    .header h1 { margin: 0; font-size: 24px; }
    .header .version {
        margin-top: 6px; font-size: 14px; opacity: 0.9;
    }
    .container { max-width: 900px; margin: 0 auto; padding: 24px 40px 60px; }
    .main-title {
        font-size: 24px; color: #1a1a1a; text-align: center;
        margin: 8px 0 28px; font-weight: 700;
    }
    .section-title {
        font-size: 20px; color: #2C89E6; border-left: 4px solid #2C89E6;
        padding-left: 12px; margin: 36px 0 18px;
    }
    .lib-entry {
        margin-bottom: 28px;
    }
    .lib-name { font-size: 16px; font-weight: 600; color: #222; }
    .lib-version {
        font-size: 13px; font-weight: 400; color: #888; margin-left: 6px;
    }
    .lib-home { margin-top: 4px; font-size: 13px; word-break: break-all; }
    .lib-home a { color: #2C89E6; text-decoration: none; }
    .lib-home a:hover { text-decoration: underline; }
    .lib-copy { margin-top: 4px; font-size: 13px; color: #666; }
    .lib-license-name {
        margin-top: 4px; font-size: 13px; color: #1565a8; font-weight: 500;
    }
    .lib-license-text {
        margin-top: 8px; padding: 0; background: transparent;
        border: none; font-size: 13px; color: #444;
        white-space: pre-wrap; word-wrap: break-word;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo,
                     monospace; line-height: 1.6;
    }
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>开源组件声明</title>
<style>{css}</style>
</head>
<body>
<div class="container">
    <h2 class="main-title">开源组件声明</h2>
    {render_section("第三方基础组件", third_party_libs)}
    {render_section("迁移工具（后端）", migration_libs)}
    {render_section("迁移工具（前端）", node_libs)}
</div>
</body>
</html>
"""


def main():
    master_version = get_master_version()
    print(f"主版本号: {master_version}")

    print("收集第三方基础运行时组件...")
    third_party_libs = get_third_party_libs()
    print(f"  共 {len(third_party_libs)} 个第三方组件")

    print("扫描 Python 运行时包（含传递依赖，排除开发工具）...")
    all_py = scan_all_python()
    print(f"  共 {len(all_py)} 个运行时 Python 包")

    print("扫描前端 Node 运行时包（含传递依赖，排除 devDependencies）...")
    all_node = scan_all_node()
    print(f"  共 {len(all_node)} 个运行时 Node 包")

    # 分类（本包只含迁移工具）
    migration_libs = classify_python_packages(all_py)

    for label, libs in [("第三方基础组件", third_party_libs),
                        ("迁移工具（后端）", migration_libs),
                        ("迁移工具（前端）", all_node)]:
        full = sum(1 for l in libs if len(l["license_text"]) > 60)
        print(f"{label}: {len(libs)} 个组件, 其中 {full} 个提取到完整协议文本")

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(
        generate_html(third_party_libs, migration_libs, all_node),
        encoding="utf-8"
    )
    print(f"已生成: {OUT_HTML}")


if __name__ == "__main__":
    main()
