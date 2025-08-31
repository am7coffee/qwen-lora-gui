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
    """起動時に前回実行時の実行ファイルとtmuxセッションを削除"""
    try:
        # プロジェクトルートディレクトリからの絶対パスを構築
        project_root = Path(__file__).parent
        execution_dir = project_root / "data" / "logs" / "executions"

        print(f"Cleanup target directory: {execution_dir}")

        if execution_dir.exists():
            # Windows: batファイル削除
            if sys.platform == "win32":
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
            
            # Linux: sh file cleanup and tmux session cleanup
            else:
                sh_files = list(execution_dir.glob("*.sh"))
                print(f"Found {len(sh_files)} sh files")

                for sh_file in sh_files:
                    try:
                        sh_file.unlink()
                        print(f"Deleted: {sh_file.name}")
                    except Exception as e:
                        print(f"Delete error: {sh_file.name} - {e}")

                if sh_files:
                    print(f"Cleanup completed: {len(sh_files)} sh files deleted")
                else:
                    print("No sh files to delete")
                
                # tmux session cleanup (Linux only)
                cleanup_tmux_sessions()
        else:
            print(f"Execution log directory does not exist: {execution_dir}")
    except Exception as e:
        print(f"Cleanup error: {e}")
        import traceback

        traceback.print_exc()


def cleanup_tmux_sessions():
    """Linux only: Delete tmux sessions starting with lora_"""
    import subprocess
    import shutil
    
    # Skip if tmux is not available
    if not shutil.which("tmux"):
        print("tmux not found. Skipping tmux session cleanup.")
        return
    
    try:
        # Get session list
        result = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("No tmux sessions found or failed to get session list.")
            return
        
        # Find sessions starting with lora_
        lora_sessions = []
        for line in result.stdout.split('\n'):
            if line.strip() and line.startswith('lora_'):
                session_name = line.split(':')[0]
                lora_sessions.append(session_name)
        
        print(f"Found {len(lora_sessions)} lora_ sessions")
        
        # Delete sessions
        for session_name in lora_sessions:
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    capture_output=True,
                    check=True
                )
                print(f"Deleted tmux session: {session_name}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to delete tmux session: {session_name} - {e}")
            except Exception as e:
                print(f"Tmux session delete error: {session_name} - {e}")
        
        if lora_sessions:
            print("Tmux session cleanup completed")
        else:
            print("No tmux sessions to delete")
            
    except FileNotFoundError:
        print("tmux command not found.")
    except Exception as e:
        print(f"Tmux session cleanup error: {e}")
        # Continue application even if cleanup fails


def main():
    """Main application startup"""
    # Execute cleanup on application startup
    print("=== Application Starting ===")
    print("Running execution file cleanup...")
    cleanup_execution_files()
    print("=== Cleanup Completed ===")

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

    args = parser.parse_args()

    # v3インターフェースを使用
    demo = create_parameter_ui()

    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=False,
        debug=False,
        inbrowser=not args.no_browser,
        favicon_path=str(Path(__file__).parent / "data" / "icon" / "am7coffee_gui.svg"),
    )


if __name__ == "__main__":
    main()
