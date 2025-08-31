"""
独立プロセス管理モジュール
ブラウザリロードに対応した新実装
"""

import subprocess
import sys
import json
import time
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Generator


class DetachedProcessManager:
    """独立プロセス管理クラス"""

    def __init__(
        self,
        state_file: str = "data/logs/executions/detached_process_state.json",
        log_dir: str = "data/logs/executions",
    ):
        """
        Args:
            state_file: プロセス状態を保存するファイルパス
            log_dir: ログファイルを保存するディレクトリ
        """
        self.state_file = Path(state_file)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def start_process(self, command: str, command_type: str) -> Dict[str, Any]:
        """
        独立プロセスとして起動（即座に完了）

        Args:
            command: 実行するコマンド
            command_type: コマンドタイプ (precache/text_encoder/training)

        Returns:
            実行結果の辞書
        """
        # コマンドの空チェック
        if not command or not command.strip():
            return {
                "success": False,
                "message": "❌ コマンドが入力されていません",
                "empty_command": True,
            }

        # 既存プロセスチェック（ログファイルベース）
        current_state = self.load_state()
        if current_state:
            # ログファイルの存在と更新状況で判定
            log_file = current_state.get("log_file")
            if log_file and Path(log_file).exists():
                last_modified = Path(log_file).stat().st_mtime
                current_time = time.time()

                # 30秒以内に更新があれば実行中と判定
                if current_time - last_modified < 30:
                    # ログファイルの内容を確認（空または無効なコマンドの場合はクリア）
                    try:
                        with open(
                            log_file, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read(1000)  # 最初の1000文字のみチェック
                            # コマンドエラーやプロセス完了の兆候を確認
                            if (
                                "コマンドの構文が誤っています" in content
                                or "[PROCESS_COMPLETED]" in content
                                or len(content.strip()) < 10
                            ):
                                # 無効なプロセス状態をクリア
                                self.clear_state()
                            else:
                                return {
                                    "success": False,
                                    "message": f"既にプロセスが実行中です (前回のログ: {Path(log_file).name})",
                                    "already_running": True,
                                }
                    except Exception:
                        # ログファイル読み込みエラーの場合は実行中と判定
                        return {
                            "success": False,
                            "message": f"既にプロセスが実行中です (前回のログ: {Path(log_file).name})",
                            "already_running": True,
                        }
                else:
                    # 古い状態情報をクリア
                    self.clear_state()
            else:
                # ログファイルが存在しない場合もクリア
                self.clear_state()

        # ログファイル作成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"{command_type}_{timestamp}.log"

        # ログファイルディレクトリとファイルを事前に作成
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch()  # 空ファイルを作成

        # バッチファイル作成（Windows用）
        if sys.platform == "win32":
            batch_file = self._create_batch_file(command_type, command, log_file)

            try:
                # 独立プロセスとして起動（シンプルな方法）
                # startコマンドで新規ウィンドウを開き、バッチファイルを実行
                process = subprocess.Popen(f'start "" "{str(batch_file)}"', shell=True)

                # プロセスが起動するまで少し待つ
                time.sleep(1.0)

                # 注意: startコマンド使用時はPIDが正確ではない
                # 実際のプロセスのPIDではなく、startコマンドのPID
                # しかし、ログファイルの存在で状態管理するため問題なし
                state = {
                    "pid": process.pid,  # これはstartコマンドのPID
                    "command_type": command_type,
                    "command": command[:500],  # 元のコマンドを保存
                    "log_file": str(log_file),
                    "started_at": datetime.now().isoformat(),
                    "status": "running",
                    "batch_file": str(batch_file),  # バッチファイルパスも保存
                }
                self.save_state(state)

                return {
                    "success": True,
                    "pid": process.pid,
                    "log_file": str(log_file),
                    "message": f"✅ {command_type}プロセスを起動しました (PID: {process.pid})",
                }

            except Exception as e:
                return {"success": False, "message": f"❌ プロセス起動エラー: {str(e)}"}
        else:
            return {"success": False, "message": "❌ Linux/Mac環境は未対応です"}

    def stop_process(self) -> str:
        """
        プロセス強制停止（停止信号ファイルを作成）

        Returns:
            結果メッセージ
        """
        state = self.load_state()

        if not state:
            return "❌ 実行中のプロセスがありません"

        command_type = state.get("command_type", "不明")
        log_file = state.get("log_file", "")

        if not log_file:
            return "❌ ログファイル情報がありません"

        # プロセス強制終了を実行（停止信号ファイルを作成）
        try:
            # 1. 停止信号ファイルを作成
            log_path = Path(log_file)
            stop_signal_file = log_path.parent / f"{command_type}_stop_signal.txt"

            try:
                # 停止信号ファイルを作成（Windowsファイルハンドルを使用）
                # open()を使って明示的にファイルを作成し、すぐに閉じる
                with open(stop_signal_file, "w", encoding="utf-8") as f:
                    f.write("STOP\n")
                    f.flush()  # バッファを強制的にフラッシュ
                    os.fsync(f.fileno())  # OSレベルでファイルを同期

                # ログファイルにも終了マーカーを追記（バックアップ）
                if log_path.exists():
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write("\n[USER_TERMINATED]\n[PROCESS_COMPLETED]\n")
                    except Exception:
                        pass  # ログファイルへの書き込みが失敗しても続行

                # Linux環境でtmuxセッションがある場合は終了
                if sys.platform != "win32" and "session_name" in state:
                    session_name = state["session_name"]
                    if shutil.which("tmux"):
                        try:
                            # tmuxセッションを終了
                            subprocess.run(
                                ["tmux", "kill-session", "-t", session_name],
                                capture_output=True
                            )
                        except Exception:
                            pass  # エラーは無視（既に終了している可能性）
                
                # プロセス状態をクリア
                self.clear_state()

                return f"✅ {command_type}プロセスに停止信号を送信しました"

            except Exception as e:
                return f"❌ 停止信号の送信に失敗: {str(e)}"

        except Exception as e:
            self.clear_state()
            return f"❌ 強制終了エラー: {str(e)}"

    def monitor_log(
        self, log_file: Optional[str] = None, timeout_minutes: int = 60
    ) -> Generator[str, None, None]:
        """
        ログファイルを監視してリアルタイム出力

        Args:
            log_file: ログファイルパス（省略時は現在のプロセスのログ）
            timeout_minutes: タイムアウト時間（分）

        Yields:
            ログ内容
        """
        # ログファイル決定
        if not log_file:
            state = self.load_state()
            if not state or not state.get("log_file"):
                yield "❌ ログファイルが見つかりません"
                return
            log_file = state["log_file"]

        log_path = Path(log_file)

        # ログファイル待機
        wait_count = 0
        while not log_path.exists() and wait_count < 10:
            time.sleep(1)
            wait_count += 1
            if wait_count == 1:
                yield f"📁 ログファイル待機中: {log_path.name}\n"

        if not log_path.exists():
            yield f"❌ ログファイルが作成されません: {log_file}"
            return

        # ログ読み込み開始
        accumulated_content = f"📁 ログ監視開始: {log_path.name}\n{'=' * 50}\n"
        yield accumulated_content

        last_position = 0
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        last_update = start_time
        no_update_timeout = 300  # 5分間更新なしで終了

        while True:
            current_time = time.time()

            # 全体タイムアウト
            if current_time - start_time > timeout_seconds:
                accumulated_content += (
                    f"\n⏱️ タイムアウト ({timeout_minutes}分) により監視を終了しました"
                )
                yield accumulated_content
                break

            # 無更新タイムアウト
            if current_time - last_update > no_update_timeout:
                state = self.load_state()
                if state and not self.is_process_alive(state.get("pid")):
                    accumulated_content += "\n✅ プロセスが終了しました"
                    yield accumulated_content
                    self.clear_state()
                    break
                else:
                    accumulated_content += f"\n⏱️ {no_update_timeout // 60}分間更新がないため監視を終了しました"
                    yield accumulated_content
                    break

            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_position)
                    new_content = f.read()

                    if new_content:
                        last_position = f.tell()
                        last_update = current_time

                        # 終了マーカー検出
                        if "[PROCESS_COMPLETED]" in new_content:
                            content = new_content.replace(
                                "[PROCESS_COMPLETED]", ""
                            ).strip()
                            if content:
                                accumulated_content += content + "\n"
                            accumulated_content += "\n✅ プロセスが正常に完了しました"
                            yield accumulated_content
                            self.clear_state()
                            break

                        accumulated_content += new_content
                        yield accumulated_content
                    else:
                        time.sleep(0.1)  # 100ms待機

            except Exception as e:
                accumulated_content += f"\n❌ ログ読み込みエラー: {str(e)}"
                yield accumulated_content
                break

    def reconnect_log(self) -> Generator[str, None, None]:
        """
        実行中プロセスのログに再接続

        Yields:
            ログ内容またはエラーメッセージ
        """
        state = self.load_state()

        if not state:
            yield "❌ 実行中のプロセス情報がありません"
            return

        pid = state.get("pid")
        log_file = state.get("log_file")
        command_type = state.get("command_type", "不明")

        # プロセス状態確認
        if pid and self.is_process_alive(pid):
            yield f"🔄 {command_type}プロセス (PID: {pid}) のログに再接続します\n"
            yield from self.monitor_log(log_file)
        else:
            # プロセス終了済み
            self.clear_state()

            if log_file and Path(log_file).exists():
                yield f"⚠️ {command_type}プロセスは終了済みです (PID: {pid})\n"
                yield "=" * 50 + "\n【最終ログ】\n"

                # 最終ログを表示
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        # 終了マーカーを除去
                        content = content.replace("[PROCESS_COMPLETED]", "").strip()
                        yield content if content else "（ログなし）"
                except Exception as e:
                    yield f"ログ読み込みエラー: {str(e)}"

                yield "\n" + "=" * 50
            else:
                yield "❌ プロセスもログファイルも見つかりません"

    def get_process_status(self) -> Dict[str, Any]:
        """
        プロセス状態を取得（ログファイルベースで判定）

        Returns:
            状態情報の辞書
        """
        state = self.load_state()

        if not state:
            return {
                "running": False,
                "message": "実行中のプロセスなし",
                "can_stop": False,
                "can_reconnect": False,
            }

        log_file = state.get("log_file", "")
        command_type = state.get("command_type", "不明")

        if not log_file:
            self.clear_state()
            return {
                "running": False,
                "message": "プロセス情報が不正です",
                "can_stop": False,
                "can_reconnect": False,
            }

        # ログファイルの更新状況でプロセス状態を判定
        log_path = Path(log_file)

        if log_path.exists():
            # ログファイルが存在する場合
            try:
                # ファイルの最終更新時刻を確認
                last_modified = log_path.stat().st_mtime
                current_time = time.time()

                # 30秒以内に更新があればまだ実行中と判定
                if current_time - last_modified < 30:
                    elapsed = self._get_elapsed_time(state.get("started_at"))
                    return {
                        "running": True,
                        "pid": state.get("pid", 0),
                        "command_type": command_type,
                        "message": f"🟢 {command_type}実行中 ({elapsed})",
                        "can_stop": True,
                        "can_reconnect": True,
                        "log_file": log_file,
                    }
                else:
                    # [PROCESS_COMPLETED]マーカーをチェック
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if "[PROCESS_COMPLETED]" in content:
                            # 正常終了
                            self.clear_state()
                            return {
                                "running": False,
                                "command_type": command_type,
                                "message": f"✅ {command_type}完了",
                                "can_stop": False,
                                "can_reconnect": True,
                                "log_file": log_file,
                            }
                        else:
                            # 実行中だが更新が止まっている
                            elapsed = self._get_elapsed_time(state.get("started_at"))
                            return {
                                "running": True,
                                "command_type": command_type,
                                "message": f"⚠️ {command_type}実行中（応答なし）({elapsed})",
                                "can_stop": True,
                                "can_reconnect": True,
                                "log_file": log_file,
                            }
            except Exception:
                pass

        # ログファイルが存在しない
        self.clear_state()
        return {
            "running": False,
            "command_type": command_type,
            "message": f"❌ {command_type}ログファイルなし",
            "can_stop": False,
            "can_reconnect": False,
        }

    def is_process_alive(self, pid: Optional[int]) -> bool:
        """
        プロセスの生存確認（PSutil不使用）

        Args:
            pid: プロセスID

        Returns:
            生存している場合True
        """
        if not pid:
            return False

        if sys.platform == "win32":
            # Windows: OpenProcessでチェック
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid
                )
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            except Exception:
                return False
        else:
            # Linux/Mac: kill -0でチェック
            try:
                os.kill(pid, 0)
                return True
            except (ProcessLookupError, PermissionError):
                return False

    def save_state(self, state: Dict[str, Any]):
        """状態を保存"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self) -> Optional[Dict[str, Any]]:
        """状態を読み込み"""
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def clear_state(self):
        """状態をクリア"""
        if self.state_file.exists():
            try:
                self.state_file.unlink()
            except Exception:
                pass  # ファイルが使用中でも無視

    def _get_elapsed_time(self, started_at: Optional[str]) -> str:
        """経過時間を取得"""
        if not started_at:
            return "不明"

        try:
            start = datetime.fromisoformat(started_at)
            elapsed = datetime.now() - start

            # 日数がある場合
            if elapsed.days > 0:
                return f"{elapsed.days}日経過"

            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if hours > 0:
                return f"{hours}時間{minutes}分経過"
            elif minutes > 0:
                return f"{minutes}分{seconds}秒経過"
            else:
                return f"{seconds}秒経過"
        except Exception:
            return "不明"

    def _create_batch_file(
        self, command_type: str, command: str, log_file: Path
    ) -> Path:
        """Windowsバッチファイルを作成"""
        from core.config.path_resolver import PathResolver

        # PathResolverでCLI設定を取得
        path_resolver = PathResolver()
        config = self._load_cli_config()
        cli_root, cli_venv = path_resolver.get_cli_paths(config)

        # コマンドの前処理
        clean_command = self._prepare_command(command)

        # ログファイルの絶対パス取得
        abs_log_file = log_file.resolve()

        # 停止信号ファイルのパス
        stop_signal_file = abs_log_file.parent / f"{command_type}_stop_signal.txt"

        batch_content = f'''@echo off
echo ========================================
echo Starting {command_type} process
echo ========================================
echo.

echo Changing directory to CLI root...
cd /d "{cli_root}"
if errorlevel 1 (
    echo [ERROR] Failed to change directory to {cli_root} >> "{abs_log_file}"
    pause
    exit /b 1
)

echo Current directory: %CD%
echo.

echo Activating virtual environment...
if exist "{cli_venv}\\Scripts\\activate.bat" (
    call "{cli_venv}\\Scripts\\activate.bat"
) else (
    echo [ERROR] Virtual environment not found at {cli_venv} >> "{abs_log_file}"
    pause
    exit /b 1
)
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment >> "{abs_log_file}"
    pause
    exit /b 1
)

REM 停止信号ファイルを削除（前回の残骸があれば）
if exist "{stop_signal_file}" (
    del /F /Q "{stop_signal_file}" 2>nul
)

echo Executing command...
echo Command: {clean_command}
echo.
echo Stop signal file: {stop_signal_file}
echo To stop this process, create the above file
echo.

REM Pythonラッパースクリプトを作成して実行
(
echo # -*- coding: utf-8 -*-
echo import subprocess
echo import sys
echo import os
echo import time
echo from pathlib import Path
echo.
echo stop_signal = Path^(r"{stop_signal_file}"^)
echo cmd = r"{clean_command}"
echo.
echo # Process start
echo proc = subprocess.Popen^(cmd, shell=True^)
echo.
echo # Check stop signal
echo while proc.poll^(^) is None:
echo     if stop_signal.exists^(^):
echo         print^("\\n[USER_TERMINATED] Stop signal detected"^)
echo         proc.terminate^(^)
echo         time.sleep^(2^)
echo         if proc.poll^(^) is None:
echo             proc.kill^(^)
echo         # Do not delete the signal file here, let batch file handle it
echo         # to avoid file locking issues
echo         sys.exit^(1^)
echo     time.sleep^(1^)
echo.
echo sys.exit^(proc.returncode^)
) > temp_wrapper.py

python temp_wrapper.py > "{abs_log_file}" 2>&1
set EXITCODE=%ERRORLEVEL%

REM クリーンアップ
timeout /t 1 /nobreak >nul
if exist temp_wrapper.py (
    del /F /Q temp_wrapper.py 2>nul
)
if exist "{stop_signal_file}" (
    timeout /t 1 /nobreak >nul
    del /F /Q "{stop_signal_file}" 2>nul || echo Failed to delete stop signal file
)

echo.
echo [PROCESS_COMPLETED] >> "{abs_log_file}"
echo.
if %EXITCODE%==0 (
    echo Process completed successfully. Window will close in 5 seconds...
) else (
    echo Process terminated. Window will close in 5 seconds...
)
timeout /t 5 /nobreak > nul
exit
'''

        batch_file = self.log_dir / f"{command_type}_detached.bat"
        with open(batch_file, "w", encoding="shift_jis") as f:
            f.write(batch_content)

        return batch_file
    
    def _start_linux_process(self, command: str, command_type: str, log_file: Path) -> Dict[str, Any]:
        """Linux環境でのプロセス起動"""
        # シェルスクリプト作成
        shell_script = self._create_shell_script(command_type, command, log_file)
        
        try:
            # nohupで標準実行（tmux問題回避のため）
            
            # nohupでバックグラウンド実行
            process = subprocess.Popen(
                f'nohup bash "{shell_script}" > /dev/null 2>&1 &',
                shell=True
            )
            
            # プロセスが起動するまで少し待つ
            time.sleep(1.0)
            
            state = {
                "pid": process.pid,
                "command_type": command_type,
                "command": command[:500],
                "log_file": str(log_file),
                "started_at": datetime.now().isoformat(),
                "status": "running",
                "shell_script": str(shell_script),
            }
            self.save_state(state)
            
            return {
                "success": True,
                "pid": process.pid,
                "log_file": str(log_file),
                "message": f"✅ {command_type}プロセスをバックグラウンドで起動しました\n💡 実行状況: ps aux | grep musubi_tuner で確認可能",
                }
                
        except Exception as e:
            return {"success": False, "message": f"❌ Linux環境でのプロセス起動エラー: {str(e)}"}
    
    def _create_shell_script(self, command_type: str, command: str, log_file: Path) -> Path:
        """Linuxシェルスクリプトを作成"""
        from core.config.path_resolver import PathResolver
        
        # PathResolverでCLI設定を取得
        path_resolver = PathResolver()
        config = self._load_cli_config()
        cli_root, cli_venv = path_resolver.get_cli_paths(config)
        
        # コマンドの前処理
        clean_command = self._prepare_command(command)
        
        # ログファイルの絶対パス取得
        abs_log_file = log_file.resolve()
        
        # 停止信号ファイルのパス
        stop_signal_file = abs_log_file.parent / f"{command_type}_stop_signal.txt"
        
        shell_content = f'''#!/bin/bash
set -e

echo "========================================"
echo "Starting {command_type} process"
echo "========================================"
echo

# ディレクトリ変更
echo "Changing directory to CLI root..."
cd "{cli_root}"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to change directory to {cli_root}" >> "{abs_log_file}"
    exit 1
fi

echo "Current directory: $(pwd)"
echo

# 仮想環境アクティベート
echo "Activating virtual environment..."
if [ -f "{cli_venv}/bin/activate" ]; then
    source "{cli_venv}/bin/activate"
else
    echo "[ERROR] Virtual environment not found at {cli_venv}" >> "{abs_log_file}"
    exit 1
fi

# 停止信号ファイル削除
rm -f "{stop_signal_file}"

echo "Executing command..."
echo "Command: {clean_command}"
echo
echo "Stop signal file: {stop_signal_file}"
echo "To stop this process, create the above file"
echo

# Pythonラッパーで実行（停止信号監視付き）
python3 << 'EOF'
import subprocess
import sys
import os
import time
from pathlib import Path

stop_signal = Path("{stop_signal_file}")
cmd = "{clean_command}"

# プロセス開始
proc = subprocess.Popen(cmd, shell=True)

# 停止信号監視
while proc.poll() is None:
    if stop_signal.exists():
        print("\\n[USER_TERMINATED] Stop signal detected")
        proc.terminate()
        time.sleep(2)
        if proc.poll() is None:
            proc.kill()
        sys.exit(1)
    time.sleep(1)

sys.exit(proc.returncode)
EOF

EXITCODE=$?
echo "[PROCESS_COMPLETED]" >> "{abs_log_file}"

if [ $EXITCODE -eq 0 ]; then
    echo "Process completed successfully."
else
    echo "Process terminated with code $EXITCODE."
fi
'''
        
        shell_file = self.log_dir / f"{command_type}_detached.sh"
        with open(shell_file, "w", encoding="utf-8") as f:
            f.write(shell_content)
        
        # 実行権限付与
        shell_file.chmod(0o755)
        
        return shell_file

    def _prepare_command(self, command_text: str) -> str:
        """コマンドを実行用に準備"""
        # 改行を除去（複数のエスケープパターンに対応）
        # 4重バックスラッシュ（JSONエスケープされたもの）
        clean_command = command_text.replace("\\\\\r\n", " ")
        clean_command = clean_command.replace("\\\\\n", " ")
        # 2重バックスラッシュ（通常のエスケープ）
        clean_command = clean_command.replace("\\\r\n", " ")
        clean_command = clean_command.replace("\\\n", " ")
        # 通常の改行文字
        clean_command = clean_command.replace("\r\n", " ")
        clean_command = clean_command.replace("\n", " ")
        clean_command = clean_command.replace("\r", " ")

        # 連続した空白を1つにまとめる
        clean_command = " ".join(clean_command.split())

        # Windows特殊文字はバッチファイル内ではエスケープ不要
        # （バッチファイル内で直接実行するため）

        return clean_command

    def _load_cli_config(self) -> Dict[str, Any]:
        """CLI設定の読み込み"""
        config_path = Path("data/config/cli_settings.json")
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "cli_root_path": "../musubi-tuner",
            "cli_venv_path": "../musubi-tuner/venv",
            "execution_settings": {
                "log_dir": "data/logs/executions",
            },
        }


# グローバルインスタンス
detached_process_manager = DetachedProcessManager()
