"""
キューシステム起動スクリプト
"""

import sys
import json
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from apps.queue.components.utils.launcher import launch_queue_system  # noqa: E402


def load_queue_config():
    """キューシステム設定を読み込み"""
    config_path = project_root / "data" / "config" / "queue_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"設定ファイル読み込みエラー: {e}")
        return {"queue_system": {"default_port": 7862, "host": "127.0.0.1"}}


def get_port_from_config_and_args():
    """設定ファイルと引数からポート番号を決定（引数優先）"""
    parser = argparse.ArgumentParser(description="キューシステムを起動します")
    parser.add_argument(
        "--port", type=int, help="ポート番号（設定ファイルの値を上書き）"
    )
    parser.add_argument("--share", action="store_true", help="Gradio共有リンクを有効化")

    args = parser.parse_args()

    # 1. コマンドライン引数が最優先
    if args.port:
        print(f"コマンドライン引数でポート指定: {args.port}")
        return args.port, args.share

    # 2. 設定ファイルから取得
    config = load_queue_config()
    default_port = config.get("queue_system", {}).get("default_port", 7862)
    print(f"設定ファイルからポート取得: {default_port}")

    return default_port, args.share


if __name__ == "__main__":
    port, share = get_port_from_config_and_args()
    print(f"キューシステムをポート {port} で起動します...")
    launch_queue_system(port=port, share=share)
