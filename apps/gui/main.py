"""
QWEN-Image LoRA学習コマンド生成ツール
メインアプリケーション
"""

import sys
import argparse
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from apps.gui.components.parameter_collector_v4 import create_parameter_ui


def main():
    """メインアプリケーションの起動"""

    parser = argparse.ArgumentParser(
        description="QWEN-Image LoRA学習コマンド生成ツール"
    )
    parser.add_argument(
        "--port", type=int, default=7860, help="サーバーポート番号 (デフォルト: 7860)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="ブラウザの自動表示を無効にする"
    )

    args = parser.parse_args()

    # v3インターフェースを使用
    demo = create_parameter_ui()

    demo.launch(
        server_name="127.0.0.1",
        server_port=args.port,
        share=False,
        debug=False,
        inbrowser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
