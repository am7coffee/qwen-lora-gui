"""
キューシステムランチャー
"""

import sys
import webbrowser
from pathlib import Path


def launch_queue_system(port: int = 7862, host: str = "127.0.0.1", share: bool = False) -> None:
    """キューシステムを起動

    Args:
        port: ポート番号
        host: ホストアドレス
        share: 共有リンクを生成するか
    """
    # パスを追加
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # アプリケーションをインポート
    from apps.queue.components.ui.queue_app import QueueSystemApp

    # アプリケーション起動
    app = QueueSystemApp()
    interface = app.create_interface()

    # 起動メッセージ
    print("=" * 60)
    print("Qwen LoRA GUI - Queue System")
    print("=" * 60)
    print(f"Local URL: http://{host}:{port}")

    if share:
        print("共有URLを生成中...")

    # ブラウザを開く
    if not share:
        url = f"http://{'localhost' if host == '127.0.0.1' else host}:{port}"
        webbrowser.open(url)

    # Gradio起動（静的ファイル配信を有効化）
    project_root = Path(__file__).parent.parent.parent.parent.parent

    interface.launch(
        server_name=host,
        server_port=port,
        share=share,
        inbrowser=False,  # 既に手動で開いているため
        quiet=False,
        # 静的ファイルの配信設定
        allowed_paths=[str(project_root / "data" / "icon")],
        # ファビコン設定
        favicon_path=str(project_root / "data" / "icon" / "am7coffee_queue.svg"),
    )


def main():
    """CLIエントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(description="Qwen LoRA GUI Queue System")
    parser.add_argument(
        "--port", type=int, default=7862, help="ポート番号 (default: 7862)"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="ホストアドレス (default: 127.0.0.1)"
    )
    parser.add_argument("--share", action="store_true", help="共有リンクを生成")

    args = parser.parse_args()
    launch_queue_system(args.port, args.host, args.share)


if __name__ == "__main__":
    main()
