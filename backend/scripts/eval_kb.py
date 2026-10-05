"""知识库检索回归测试。

改动 data/kb/*.md、调整相似度阈值或更换 embedding 模型后，重跑本脚本确认检索行为没有退化。

用法：
    cd backend
    python scripts/eval_kb.py
"""

import re
import sys
from pathlib import Path

# 让脚本能直接 import app.*，不依赖「从 backend 目录启动」
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # 避免 Windows 控制台 GBK 编码报错

from app.services import kb_service  # noqa: E402

# (查询语句, 期望命中的文件名)；期望为 None 表示「应该检索不到任何内容」
CASES = [
    ("化学实验室几点关门", "开放时间.md"),
    ("进实验室要穿什么", "安全规范.md"),
    ("提交预约后什么时候能用", "预约规则.md"),
    ("电子显微镜怎么使用", "设备使用.md"),
    ("实验室开放时间", "开放时间.md"),
    ("今天天气怎么样", None),
    ("Python 怎么安装", None),
    ("帮我写一首诗", None),
    ("推荐几家餐厅", None),
]


def main() -> int:
    col = kb_service.get_collection()
    print(f"向量库 chunk 数：{col.count()}\n")

    print(f"{'':<6}{'查询':<22}{'期望命中':<14}{'实际命中':<22}{'结果'}")
    print("-" * 76)

    passed = 0
    for query, expect in CASES:
        text = kb_service.search(query)
        found = re.findall(r"^\[(.+?)\]$", text, re.M)

        if expect is None:
            ok = not found
            actual = "、".join(found) if found else "（空）"
        else:
            ok = expect in found
            actual = "、".join(found) if found else "（空）"

        passed += ok
        print(
            f"{'PASS' if ok else 'FAIL':<6}{query:<22}"
            f"{expect or '（应为空）':<14}{actual:<22}{'OK' if ok else '!!'}"
        )

    print("-" * 76)
    total = len(CASES)
    print(f"通过 {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
