"""`python -m agent` 入口。

让用户可以从仓库根目录直接运行 `python -m agent`，而不用记住内部文件路径。
"""

from .cli import main


if __name__ == "__main__":
    main()
