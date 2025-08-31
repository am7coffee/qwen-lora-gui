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
        "--host", type=str, default="127.0.0.1", help="バインドするホストアドレス (デフォルト: 127.0.0.1)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="ブラウザの自動表示を無効にする"
    )
    parser.add_argument(
        "--share", action="store_true", help="Gradio共有リンクを有効化"
    )

    args = parser.parse_args()

    # v3インターフェースを使用
    demo = create_parameter_ui()

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        debug=False,
        inbrowser=not args.no_browser,
        favicon_path=str(Path(__file__).parent.parent.parent / "data" / "icon" / "am7coffee_gui.svg"),
    )


if __name__ == "__main__":
    main()
