import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="contract-chat-mapping")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        print("请创建 config.yaml 后重试。")
        sys.exit(0)

    try:
        from src.config import load_config
        cfg = load_config(str(config_path))
    except Exception as e:
        print(f"加载配置失败: {e}")
        cfg = {}

    try:
        from src.orchestrator import run
        run(cfg)
    except Exception as e:
        print(f"运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
