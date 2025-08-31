"""
タスク実行エンジン
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apps.queue.components.core.models import QueueTask, TaskType
from apps.queue.components.core.slack_notifier import get_slack_notifier
from apps.queue.components.core.progress_monitor import ProgressMonitor

# CommandGeneratorをインポート
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.commands.command_generator import CommandGenerator


class TaskExecutor:
    """タスク実行エンジン"""

    def __init__(self, log_dir: str = "data/queue_system/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_process: Optional[subprocess.Popen] = None
        self.current_task: Optional[QueueTask] = None
        self._stop_flag = threading.Event()
        self.slack = get_slack_notifier()
        self.command_generator = CommandGenerator()  # CommandGeneratorのインスタンス
        self.cli_config = self._load_cli_config()  # CLI環境設定を読み込み

    def _load_cli_config(self) -> Dict[str, Any]:
        """CLI環境設定を読み込み"""
        config_path = Path("data/config/cli_settings.json")

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        # デフォルト設定
        return {
            "cli_root_path": "../musubi-tuner",
            "cli_venv_path": "../musubi-tuner/venv",
        }

    def _get_cli_python_path(self) -> Path:
        """CLI環境のPythonパスを取得"""
        cli_venv = Path(self.cli_config["cli_venv_path"]).resolve()

        if sys.platform == "win32":
            return cli_venv / "Scripts" / "python.exe"
        else:
            return cli_venv / "bin" / "python"

    def _get_cli_accelerate_path(self) -> Path:
        """CLI環境のaccelerateパスを取得"""
        cli_venv = Path(self.cli_config["cli_venv_path"]).resolve()

        if sys.platform == "win32":
            return cli_venv / "Scripts" / "accelerate.exe"
        else:
            return cli_venv / "bin" / "accelerate"

    def execute_task(self, task: QueueTask) -> Tuple[bool, Optional[str]]:
        """タスクを実行

        Returns:
            (success, error_message)
        """
        self.current_task = task
        self._stop_flag.clear()

        # ログファイル設定
        log_file = self._create_log_file(task)
        task.log_file = str(log_file)

        try:
            # タスクタイプごとに順次実行
            for i, task_type in enumerate(task.task_types):
                if self._stop_flag.is_set():
                    return False, "タスクが中断されました"

                task.current_subtask_index = i

                # Slack通知（タスク開始）
                display_name = TaskType.DISPLAY_NAMES.get(task_type, task_type)
                self.slack.notify_task_start(task.id, task.preset_name, display_name)

                # コマンド生成と実行
                command = self._generate_command(task, task_type)
                if not command:
                    return False, f"コマンド生成に失敗: {task_type}"

                success = self._execute_command(command, log_file, task_type)
                if not success:
                    return False, f"{display_name}の実行に失敗しました"

            return True, None

        except Exception as e:
            return False, f"実行エラー: {str(e)}"
        finally:
            self.current_process = None
            self.current_task = None

    def stop_execution(self) -> None:
        """実行を停止"""
        self._stop_flag.set()
        if self.current_process:
            try:
                self.current_process.terminate()
                time.sleep(2)
                if self.current_process.poll() is None:
                    self.current_process.kill()
            except Exception:
                pass

    def _generate_command(self, task: QueueTask, task_type: str) -> Optional[List[str]]:
        """コマンドを生成（プリセットに保存されたコマンドを優先使用）"""
        # プリセットデータの確認
        if not task.preset_data:
            return None

        # プリセットに保存されたコマンドがある場合は優先使用
        commands = task.preset_data.get("commands", {})
        if commands and task_type in commands:
            # 保存されたコマンドリストを使用
            command = commands[task_type].copy()  # リストをコピーして使用
        else:
            # 後方互換性：コマンドがない場合は従来の方法で生成
            params_raw = task.preset_data.get("parameters", {})

            # パラメータを変換（enabled/valueの形式からシンプルな形式へ）
            params: Dict[str, Any] = {}
            for key, param_data in params_raw.items():
                if key == "optimizer_args":
                    # optimizer_argsは特別処理（ネストされた構造）
                    optimizer_args = {}
                    if isinstance(param_data, dict):
                        for arg_key, arg_data in param_data.items():
                            if isinstance(arg_data, dict) and arg_data.get("enabled"):
                                optimizer_args[arg_key] = arg_data.get("value")
                    if optimizer_args:
                        params[key] = optimizer_args
                elif isinstance(param_data, dict):
                    if param_data.get("enabled"):
                        value = param_data.get("value")
                        # value2がある場合（解像度など）の処理
                        value2 = param_data.get("value2")
                        if key == "resolution" and value2 is not None and value2 != "":
                            params[key] = f"{value},{value2}"
                        else:
                            # 値のクォートを除去（プリセットファイルにクォートが含まれる場合）
                            if isinstance(value, str):
                                value = value.strip()
                                if value.startswith('"') and value.endswith('"'):
                                    value = value[1:-1]
                                elif value.startswith("'") and value.endswith("'"):
                                    value = value[1:-1]
                            params[key] = value
                else:
                    params[key] = param_data

            # CommandGeneratorを使用してコマンドリストを生成
            command = self.command_generator.generate_command_as_list(task_type, params)

        if not command:
            return None

        # CLI環境のPython/accelerateに置き換え
        if command[0] == sys.executable:
            # Pythonコマンドの場合、CLI環境のPythonに置き換え
            command[0] = str(self._get_cli_python_path())
            # Pythonコマンドに -u オプションを追加（アンバッファードモード）
            command.insert(1, "-u")
        elif command[0] == "accelerate":
            # accelerateコマンドの場合、CLI環境のaccelerateに置き換え
            command[0] = str(self._get_cli_accelerate_path())

        # スクリプトパスをCLI環境の相対パスから絶対パスに変換
        cli_root = Path(self.cli_config["cli_root_path"]).resolve()
        for i, arg in enumerate(command):
            if arg.startswith("src/musubi_tuner/"):
                command[i] = str(cli_root / arg)

        return command

    def _add_param_to_command(
        self, command: List[str], params: Dict[str, Any], key: str
    ) -> None:
        """パラメータをコマンドに追加"""
        if key in params:
            param_data = params[key]
            if isinstance(param_data, dict) and param_data.get("enabled"):
                value = param_data.get("value")
                if value is not None:
                    # パラメータ名変換（dataset_config -> --dataset_config）
                    command.extend([f"--{key}", str(value)])

    def _execute_command(
        self, command: List[str], log_file: Path, task_type: str
    ) -> bool:
        """コマンドを実行"""
        try:
            # CLI環境のルートディレクトリ
            cli_root = Path(self.cli_config["cli_root_path"]).resolve()

            # ログヘッダーを書き込み
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(
                    f"実行開始: {TaskType.DISPLAY_NAMES.get(task_type, task_type)}\n"
                )
                f.write(f"時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"作業ディレクトリ: {cli_root}\n")
                f.write(f"コマンド: {' '.join(command)}\n")
                f.write(f"{'=' * 60}\n\n")
                f.flush()  # ヘッダーも即座に書き込む

            # 学習実行かつ進捗通知が有効な場合、監視を開始
            progress_monitor = None
            monitor_thread = None

            if (
                task_type == "training"
                and self.slack.config.notify_progress
                and self.slack.config.progress_interval > 0
                and self.current_task
            ):
                progress_monitor = ProgressMonitor(
                    log_file=log_file,
                    task_id=self.current_task.id,
                    task_name=self.current_task.preset_name,
                    interval=self.slack.config.progress_interval,
                    slack_notifier=self.slack,
                )

                monitor_thread = threading.Thread(
                    target=progress_monitor.monitor_progress, daemon=True
                )
                monitor_thread.start()

            # 全プラットフォームで標準実行を使用（出力の完全性を優先）
            if sys.platform == "win32":
                return self._execute_with_pseudo_tty(
                    command, log_file, cli_root, progress_monitor, monitor_thread
                )
            else:
                # Linux環境でも標準実行を使用（tmux出力問題を回避）
                return self._execute_standard(
                    command, log_file, cli_root, progress_monitor, monitor_thread
                )

        except Exception as e:
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\nエラー: {str(e)}\n")
            return False

    def _execute_with_pseudo_tty(
        self,
        command: List[str],
        log_file: Path,
        cli_root: Path,
        progress_monitor,
        monitor_thread,
    ) -> bool:
        """擬似TTYを使用してコマンドを実行（Windows用）

        Note:
            - Windows環境では小さな320x240のコンソールウィンドウを生成
            - このウィンドウは表示内容なし（ログ書き出し専用）
            - バッファリングを完全に無効化してリアルタイムログ出力を実現
        """
        try:
            # Python出力のバッファリングを無効化するための環境変数
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            # creationflags で擬似コンソールを作成
            import subprocess

            # Windows用のウィンドウサイズ設定
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()

                # Windows APIの定数を直接定義（subprocess モジュールには一部の定数がない）
                STARTF_USESHOWWINDOW = 0x00000001
                SW_MINIMIZE = 6

                # ウィンドウサイズと位置を設定
                startupinfo.dwFlags = STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = SW_MINIMIZE  # 最小化で開始

                # コンソールウィンドウのサイズを制御する別の方法
                # ウィンドウ作成後にWin32 APIで制御する必要がある

            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                bufsize=0,
                cwd=cli_root,
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE
                if sys.platform == "win32"
                else 0,
                startupinfo=startupinfo,  # ウィンドウ設定を追加
                universal_newlines=False,
            )

            # Windows環境でコンソールウィンドウのサイズを最小限に設定
            if sys.platform == "win32" and self.current_process:
                try:
                    import ctypes
                    from ctypes import wintypes
                    import time

                    # ウィンドウが作成されるまで少し待つ
                    time.sleep(0.2)

                    # Win32 API関数と定数の定義
                    user32 = ctypes.windll.user32

                    # EnumWindowsのコールバック関数型
                    EnumWindowsProc = ctypes.WINFUNCTYPE(
                        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM
                    )

                    # プロセスIDからウィンドウを探す
                    target_pid = self.current_process.pid
                    found_hwnd = None

                    def enum_callback(hwnd, lparam):
                        """ウィンドウ列挙のコールバック"""
                        nonlocal found_hwnd
                        # ウィンドウのプロセスIDを取得
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                        # 対象プロセスのウィンドウが見つかった場合
                        if pid.value == target_pid:
                            # ウィンドウのクラス名を取得
                            class_name = ctypes.create_unicode_buffer(256)
                            user32.GetClassNameW(hwnd, class_name, 256)
                            # コンソールウィンドウを探す
                            if "ConsoleWindow" in class_name.value or hwnd:
                                found_hwnd = hwnd
                                return False  # 列挙を停止
                        return True  # 列挙を継続

                    # ウィンドウを列挙
                    enum_proc = EnumWindowsProc(enum_callback)
                    user32.EnumWindows(enum_proc, 0)

                    if found_hwnd:
                        # Win32 API定数
                        SW_MINIMIZE = 6
                        SWP_NOACTIVATE = 0x0010
                        SWP_NOZORDER = 0x0004
                        SWP_FRAMECHANGED = 0x0020

                        # 画面サイズを取得
                        screen_width = user32.GetSystemMetrics(0)
                        screen_height = user32.GetSystemMetrics(1)

                        # 最小限のウィンドウサイズ（復元時用）
                        # コンソールの最小サイズは約120文字 x 10行
                        window_width = 400  # 幅400ピクセル（最小限）
                        window_height = 200  # 高さ200ピクセル（最小限）

                        # まず、ウィンドウサイズと位置を設定（復元時のため）
                        user32.SetWindowPos(
                            found_hwnd,
                            0,  # HWND_TOP
                            screen_width - window_width - 30,  # 画面右下隅
                            screen_height - window_height - 80,  # タスクバー考慮
                            window_width,
                            window_height,
                            SWP_NOACTIVATE | SWP_NOZORDER | SWP_FRAMECHANGED,
                        )

                        # その後、最小化を維持
                        user32.ShowWindow(found_hwnd, SW_MINIMIZE)

                        # タイトル設定（タスクバーで識別しやすく）
                        if self.current_task:
                            title = f"Log - {self.current_task.preset_name[:15]}"
                            user32.SetWindowTextW(found_hwnd, title)

                except Exception:
                    # エラーが発生しても処理は継続
                    pass  # ログへの記録を避けて静かに継続

            # リアルタイムでログファイルに書き込む（行ごとに処理）
            import io

            # 複数のエンコーディングを試みる
            encodings = (
                ["utf-8", "cp932", "shift_jis"]
                if sys.platform == "win32"
                else ["utf-8"]
            )

            with open(log_file, "a", encoding="utf-8") as f:
                # TextIOWrapperで行単位の読み取りを可能にする
                if self.current_process.stdout is None:
                    return False

                text_stream = None
                for encoding in encodings:
                    try:
                        text_stream = io.TextIOWrapper(
                            self.current_process.stdout,
                            encoding=encoding,
                            errors="replace",
                            line_buffering=True,  # 行バッファリングを有効化
                        )
                        break
                    except Exception:
                        continue

                if text_stream is None:
                    # デフォルトのエンコーディングを使用
                    text_stream = io.TextIOWrapper(
                        self.current_process.stdout,
                        encoding="utf-8",
                        errors="replace",
                        line_buffering=True,
                    )

                try:
                    for line in iter(text_stream.readline, ""):
                        if self._stop_flag.is_set():
                            self.current_process.terminate()
                            time.sleep(2)
                            if self.current_process.poll() is None:
                                self.current_process.kill()
                            if progress_monitor:
                                progress_monitor.stop_monitoring()
                            f.write("\n[プロセスが中断されました]\n")
                            f.flush()
                            return False

                        # UTF-8でファイルに書き込み
                        f.write(line)
                        f.flush()

                        # プロセスの終了チェック
                        if self.current_process.poll() is not None:
                            # 残りの行を読み取る（重要！すべて読み取らないと終了コードが取得できない場合がある）
                            try:
                                remaining_lines = text_stream.readlines()
                                for remaining_line in remaining_lines:
                                    f.write(remaining_line)
                            except Exception:
                                pass  # プロセス終了時の読み取りエラーは無視
                            f.flush()
                            break
                except Exception as read_error:
                    # 読み取りエラー（プロセスが強制終了された場合など）
                    f.write(f"\n[読み取りエラー: {str(read_error)}]\n")
                    f.flush()

            # プロセスが終了するまで待機（重要！）
            return_code = self.current_process.wait()

            # 100%進捗通知のため6秒待機してから監視停止
            if progress_monitor:
                time.sleep(6)
                progress_monitor.stop_monitoring()
                if monitor_thread:
                    monitor_thread.join(timeout=1)

            # ログファイルから成功を判定する補助関数
            def check_log_for_success(log_file: Path) -> bool:
                """ログファイルから成功の兆候を探す"""
                success_patterns = [
                    "successfully saved",
                    "save trained model",
                    "training completed",
                    "saved safetensors",
                    "model saved",
                    "caching completed",
                    "latents cached",
                    "text encoder outputs cached",
                    "100%|",  # 進捗が100%
                    "done!",  # 完了メッセージ
                    "finished",  # 終了メッセージ
                    "cache saved",  # キャッシュ保存完了
                    "latent saved",  # 潜在変数保存完了
                    "all latents saved",  # すべての潜在変数保存完了
                    "te output saved",  # TEアウトプット保存完了
                    "text encoder output saved",  # テキストエンコーダー出力保存
                    "vae encoded",  # VAEエンコード完了
                ]

                error_patterns = [
                    "error",
                    "exception",
                    "traceback",
                    "failed",
                    "cuda out of memory",
                    "killed",
                ]

                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()

                        # エラーパターンをチェック
                        for pattern in error_patterns:
                            if pattern in content:
                                # ただし、一部の無害なエラーは除外
                                if "wandb" in content and "error" in pattern:
                                    continue  # wandbのエラーは無視
                                if "warning" in content and "error" in pattern:
                                    continue  # 警告レベルのエラーは無視
                                return False

                        # 成功パターンをチェック
                        for pattern in success_patterns:
                            if pattern in content:
                                return True

                except Exception:
                    pass

                return False

            # 終了コードの解釈（より柔軟な判定）
            if return_code is None:
                # プロセスがまだ実行中（通常ありえない）
                return False
            elif return_code == 0:
                # 正常終了
                return True
            elif return_code == 1:
                # 終了コード1の場合、ログを確認して判定
                # 一部のPythonスクリプトは正常終了でも1を返すことがある
                log_success = check_log_for_success(log_file)
                with open(log_file, "a", encoding="utf-8") as f:
                    if log_success:
                        f.write(
                            "\n[注意] 終了コード1ですが、ログから正常終了と判断しました\n"
                        )
                        return True
                    else:
                        f.write(
                            f"\n[プロセスがエラーで終了しました: 終了コード {return_code}]\n"
                        )
                        return False
            elif return_code < 0:
                # シグナルによる終了（Unix）またはエラー終了
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"\n[プロセスが異常終了しました: 終了コード {return_code}]\n"
                    )
                return False
            else:
                # その他のエラー終了コード
                # ログを確認して最終判定
                log_success = check_log_for_success(log_file)
                with open(log_file, "a", encoding="utf-8") as f:
                    if log_success:
                        f.write(
                            f"\n[注意] 終了コード{return_code}ですが、ログから正常終了と判断しました\n"
                        )
                        return True
                    else:
                        f.write(
                            f"\n[プロセスがエラーで終了しました: 終了コード {return_code}]\n"
                        )
                        return False

        except Exception as e:
            print(f"Pseudo-TTY execution error: {e}")
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\n[実行エラー: {str(e)}]\n")
            return False

    def _execute_standard(
        self,
        command: List[str],
        log_file: Path,
        cli_root: Path,
        progress_monitor,
        monitor_thread,
    ) -> bool:
        """標準的な方法でコマンドを実行（Unix系用）"""
        # Python出力のバッファリングを無効化するための環境変数
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        self.current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
            cwd=cli_root,
            env=env,
        )

        # 出力読み取り用スレッドを開始
        output_thread = threading.Thread(
            target=self._read_output_and_save,
            args=(self.current_process, log_file),
            daemon=True,
        )
        output_thread.start()

        # プロセス監視
        while True:
            if self._stop_flag.is_set():
                self.current_process.terminate()
                time.sleep(2)
                if self.current_process.poll() is None:
                    self.current_process.kill()
                if progress_monitor:
                    progress_monitor.stop_monitoring()
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write("\n[プロセスが中断されました]\n")
                return False

            ret = self.current_process.poll()
            if ret is not None:
                output_thread.join(timeout=2)
                if progress_monitor:
                    progress_monitor.stop_monitoring()
                    if monitor_thread:
                        monitor_thread.join(timeout=1)

                # ログファイルから成功を判定する補助関数（Windows版と同じ）
                def check_log_for_success_unix(log_file: Path) -> bool:
                    """ログファイルから成功の兆候を探す"""
                    success_patterns = [
                        "successfully saved",
                        "save trained model",
                        "training completed",
                        "saved safetensors",
                        "model saved",
                        "caching completed",
                        "latents cached",
                        "text encoder outputs cached",
                        "100%|",
                        "done!",
                        "finished",
                        "cache saved",
                        "latent saved",
                        "all latents saved",
                        "te output saved",
                        "text encoder output saved",
                        "vae encoded",
                    ]

                    error_patterns = [
                        "error",
                        "exception",
                        "traceback",
                        "failed",
                        "cuda out of memory",
                        "killed",
                    ]

                    try:
                        with open(
                            log_file, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read().lower()

                            for pattern in error_patterns:
                                if pattern in content:
                                    if "wandb" in content and "error" in pattern:
                                        continue
                                    if "warning" in content and "error" in pattern:
                                        continue
                                    return False

                            for pattern in success_patterns:
                                if pattern in content:
                                    return True

                    except Exception:
                        pass

                    return False

                # 終了コードの解釈（より柔軟な判定）
                if ret == 0:
                    return True
                elif ret == 1:
                    log_success = check_log_for_success_unix(log_file)
                    with open(log_file, "a", encoding="utf-8") as f:
                        if log_success:
                            f.write(
                                "\n[注意] 終了コード1ですが、ログから正常終了と判断しました\n"
                            )
                            return True
                        else:
                            f.write(
                                f"\n[プロセスがエラーで終了しました: 終了コード {ret}]\n"
                            )
                            return False
                elif ret < 0:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"\n[プロセスが異常終了しました: 終了コード {ret}]\n")
                    return False
                else:
                    log_success = check_log_for_success_unix(log_file)
                    with open(log_file, "a", encoding="utf-8") as f:
                        if log_success:
                            f.write(
                                f"\n[注意] 終了コード{ret}ですが、ログから正常終了と判断しました\n"
                            )
                            return True
                        else:
                            f.write(
                                f"\n[プロセスがエラーで終了しました: 終了コード {ret}]\n"
                            )
                            return False

            time.sleep(1)

    def _execute_with_tmux(
        self,
        command: List[str],
        log_file: Path,
        cli_root: Path,
        progress_monitor,
        monitor_thread,
    ) -> bool:
        """tmuxセッションでコマンドを実行（Linux/Unix用）
        
        tmuxを使用することで、SSH切断後も処理を継続できる。
        セッション内の出力を定期的にキャプチャしてログファイルに保存。
        """
        try:
            # セッション名を生成（タスクIDとタイムスタンプを使用）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_name = f"queue_{self.current_task.id if self.current_task else 'unknown'}_{timestamp}"
            
            # 既存のセッションをチェック（名前衝突回避）
            check_session = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True,
                text=True
            )
            
            if check_session.returncode == 0:
                # 既存セッションがある場合は別名にする
                import random
                session_name = f"{session_name}_{random.randint(1000, 9999)}"
            
            # Python出力のバッファリングを無効化
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            
            # コマンドを文字列に変換
            command_str = " ".join(command)
            
            # tmuxセッションを作成してコマンドを実行
            # -d: デタッチモード, -s: セッション名, -c: 作業ディレクトリ
            # trap設定でプロセス管理を改善（クォートエスケープ修正）
            trap_command = f'trap "echo Terminating all child processes...; kill 0" EXIT TERM INT; {command_str}'
            tmux_create_cmd = [
                "tmux", "new-session", "-d", "-s", session_name,
                "-c", str(cli_root),
                f"PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 bash -c '{trap_command}'"
            ]
            
            # セッション作成
            create_result = subprocess.run(
                tmux_create_cmd,
                capture_output=True,
                text=True,
                cwd=cli_root
            )
            
            if create_result.returncode != 0:
                # tmuxセッション作成失敗時は標準実装にフォールバック
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n[警告] tmuxセッション作成失敗: {create_result.stderr}\n")
                    f.write("[情報] 標準実行モードにフォールバックします\n")
                return self._execute_standard(
                    command, log_file, cli_root, progress_monitor, monitor_thread
                )
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[情報] tmuxセッション '{session_name}' で実行開始\n")
                f.flush()
            
            # セッション監視
            return self._monitor_tmux_session(
                session_name, log_file, progress_monitor, monitor_thread
            )
            
        except Exception as e:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[エラー] tmux実行エラー: {str(e)}\n")
                f.write("[情報] 標準実行モードにフォールバックします\n")
            # エラー時は標準実装にフォールバック
            return self._execute_standard(
                command, log_file, cli_root, progress_monitor, monitor_thread
            )
    
    def _monitor_tmux_session(
        self,
        session_name: str,
        log_file: Path,
        progress_monitor,
        monitor_thread,
    ) -> bool:
        """tmuxセッションを監視してログを取得"""
        last_output = ""
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            # 停止フラグチェック
            if self._stop_flag.is_set():
                # セッションにCtrl+Cを送信
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, "C-c"],
                    capture_output=True
                )
                time.sleep(2)
                
                # セッションを強制終了
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    capture_output=True
                )
                
                if progress_monitor:
                    progress_monitor.stop_monitoring()
                
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write("\n[プロセスが中断されました]\n")
                return False
            
            # セッション存在確認
            check_result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True,
                text=True
            )
            
            if check_result.returncode != 0:
                # セッションが終了している
                if progress_monitor:
                    progress_monitor.stop_monitoring()
                    if monitor_thread:
                        monitor_thread.join(timeout=1)
                
                # 最終的なログ内容を取得
                self._capture_tmux_output(session_name, log_file, last_output)
                
                # ログから成功を判定
                return self._check_log_for_success(log_file)
            
            # セッション出力をキャプチャ
            try:
                last_output = self._capture_tmux_output(session_name, log_file, last_output)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"\n[エラー] tmux出力取得エラーが連続: {str(e)}\n")
                    break
            
            time.sleep(1)
        
        # エラーによる終了
        if progress_monitor:
            progress_monitor.stop_monitoring()
        return False
    
    def _capture_tmux_output(
        self,
        session_name: str,
        log_file: Path,
        last_output: str
    ) -> str:
        """tmuxセッションの出力をキャプチャしてログに追記"""
        # tmux capture-paneで出力を取得
        capture_result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-"],
            capture_output=True,
            text=True,
            errors="replace"
        )
        
        if capture_result.returncode == 0:
            current_output = capture_result.stdout
            
            # 新しい出力部分のみを抽出
            if len(current_output) > len(last_output):
                new_lines = current_output[len(last_output):]
                if new_lines.strip():
                    with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                        f.write(new_lines)
                        f.flush()
            
            return current_output
        
        return last_output
    
    def _check_log_for_success(self, log_file: Path) -> bool:
        """タスク種別に応じた成功判定"""
        
        # 1. プロセス終了コード判定（全タスク共通）
        # TODO: tmux環境でのプロセス終了コード取得問題のため一時的にコメントアウト
        # if not self._check_process_exit_code():
        #     return False  # 異常終了 = エラー
        
        # 2. タスク種別による判定
        if self.current_task and self.current_task.current_subtask:
            task_type = self.current_task.current_subtask
            
            # キャッシュ生成タスク：画像処理件数で判定
            if task_type in ["latent_cache", "te_cache"]:
                return self._check_completion_by_count(log_file)
            
            # 学習タスク：進捗バー完了で判定
            elif task_type == "training":
                return self._check_training_completion(log_file)
        
        # 旧来の成功パターン判定（フォールバック）
        return self._check_legacy_patterns(log_file)

    def _check_process_exit_code(self) -> bool:
        """プロセス終了コードをチェック"""
        if self.current_process is None:
            return False
        
        # プロセスが終了していない場合は待機
        if self.current_process.poll() is None:
            return False
        
        # 終了コード0 = 正常終了
        return self.current_process.returncode == 0

    def _check_completion_by_count(self, log_file: Path) -> bool:
        """画像枚数と処理済み件数を照合"""
        import re
        
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            
            # 画像枚数を取得
            found_match = re.search(r"found (\d+) images", content)
            if not found_match:
                return False
            expected_count = int(found_match.group(1))
            
            # 最終処理件数を取得 (進捗表示の最後の数値)
            progress_matches = re.findall(r"(\d+)it \[", content)
            if not progress_matches:
                return False
            final_count = int(progress_matches[-1])
            
            # 処理件数が期待値と一致するかチェック
            return final_count == expected_count
            
        except Exception:
            return False

    def _check_training_completion(self, log_file: Path) -> bool:
        """学習タスクの完了を進捗バーで判定"""
        import re
        
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            
            # 学習完了パターンを検索
            # steps: 100%|██████████| 640/640 [19:28<00:00, 1.83s/it, avr_loss=0.0778]
            training_complete_pattern = r"steps:\s*100%\|.*\|\s*\d+/\d+\s*\["
            
            if re.search(training_complete_pattern, content):
                return True
            
            return False
            
        except Exception:
            return False

    def _check_legacy_patterns(self, log_file: Path) -> bool:
        """旧来の成功パターン判定（フォールバック用）"""
        success_patterns = [
            "successfully saved",
            "save trained model", 
            "training completed",
            "saved safetensors",
            "model saved",
            "caching completed",
            "latents cached",
            "text encoder outputs cached",
            "100%|",
            "done!",
            "finished",
            "cache saved",
            "latent saved",
            "all latents saved",
            "te output saved",
            "text encoder output saved",
            "vae encoded",
        ]
        
        error_patterns = [
            "error",
            "exception", 
            "traceback",
            "failed",
            "cuda out of memory",
            "killed",
        ]
        
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                
                # エラーパターンのチェック（wandbやwarning関連は除外）
                for pattern in error_patterns:
                    if pattern in content:
                        if "wandb" in content and "error" in pattern:
                            continue
                        if "warning" in content and "error" in pattern:
                            continue
                        return False
                
                # 成功パターンのチェック
                for pattern in success_patterns:
                    if pattern in content:
                        return True
        
        except Exception:
            pass
        
        return False

    def _read_output_and_save(self, process: subprocess.Popen, log_file: Path):
        """プロセス出力を読み取ってファイルに保存"""

        # Windowsではcp932、それ以外はutf-8でデコードを試みる
        encodings = (
            ["utf-8", "cp932", "shift_jis"] if sys.platform == "win32" else ["utf-8"]
        )

        with open(log_file, "ab") as f:  # バイナリモードで開く
            if process.stdout:
                for line_bytes in process.stdout:
                    # 複数のエンコーディングでデコードを試みる
                    decoded_line = None
                    for encoding in encodings:
                        try:
                            decoded_line = line_bytes.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue

                    # デコードできなかった場合は、エラーを無視してデコード
                    if decoded_line is None:
                        decoded_line = line_bytes.decode("utf-8", errors="replace")

                    # UTF-8でファイルに書き込み
                    f.write(decoded_line.encode("utf-8"))
                    # バッファを即座にディスクに書き込む（リアルタイム監視のため）
                    f.flush()

    def _create_log_file(self, task: QueueTask) -> Path:
        """ログファイルを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{task.id}_{task.preset_name}_{timestamp}.log"
        log_file = self.log_dir / filename

        with open(log_file, "w", encoding="utf-8") as f:
            f.write("キュータスク実行ログ\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"タスクID: {task.id}\n")
            f.write(f"プリセット: {task.preset_name}\n")
            f.write(f"実行タスク: {task.display_tasks}\n")
            f.write(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'=' * 60}\n")

        return log_file


# グローバルインスタンス管理
_task_executor_instance: Optional[TaskExecutor] = None


def get_task_executor() -> TaskExecutor:
    """シングルトンインスタンスを取得"""
    global _task_executor_instance
    if _task_executor_instance is None:
        _task_executor_instance = TaskExecutor()
    return _task_executor_instance
