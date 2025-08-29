"""
QWEN-Image LoRA学習コマンド生成ツール
メインアプリケーション
"""

import sys
import argparse
from pathlib import Path

# appsディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from apps.gui.components.parameter_collector_v4 import create_parameter_ui


def cleanup_execution_files():
    """起動時に前回実行時のbatファイルを削除"""
    try:
        # プロジェクトルートディレクトリからの絶対パスを構築
        project_root = Path(__file__).parent
        execution_dir = project_root / "data" / "logs" / "executions"

        print(f"クリーンアップ対象ディレクトリ: {execution_dir}")

        if execution_dir.exists():
            bat_files = list(execution_dir.glob("*.bat"))
            print(f"発見されたbatファイル: {len(bat_files)}個")

            for bat_file in bat_files:
                try:
                    bat_file.unlink()
                    print(f"削除: {bat_file.name}")
                except Exception as e:
                    print(f"削除エラー: {bat_file.name} - {e}")

            if bat_files:
                print(f"削除完了: {len(bat_files)}個のbatファイル")
            else:
                print("削除対象のbatファイルはありませんでした")
        else:
            print(f"実行ログディレクトリが存在しません: {execution_dir}")
    except Exception as e:
        print(f"クリーンアップエラー: {e}")
        import traceback

        traceback.print_exc()


def main():
    """メインアプリケーションの起動"""
    # アプリケーション起動時にクリーンアップ実行
    print("=== アプリケーション起動開始 ===")
    print("batファイルクリーンアップを実行します...")
    cleanup_execution_files()
    print("=== クリーンアップ完了 ===")

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
        favicon_path=str(Path(__file__).parent / "data" / "icon" / "am7coffee_gui.svg"),
    )


if __name__ == "__main__":
    main()
