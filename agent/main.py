"""Agent 包内主入口。

这个文件放在 `agent/` 目录中，和完整实现保持在同一个包里。
用户既可以运行 `python -m agent`，也可以运行 `python agent/main.py`。
"""

from __future__ import annotations

import sys
from pathlib import Path


# 直接运行 `python agent/main.py` 时，Python 会把 agent/ 加入搜索路径。
# 这里补充仓库根目录，确保绝对导入 `agent.cli` 稳定可用。
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.cli import main


if __name__ == "__main__":
    main()
