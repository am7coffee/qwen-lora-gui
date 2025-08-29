"""
ストリーミングログ管理モジュール
リアルタイムでプロセス出力を管理・表示する
"""

import threading
import time
from collections import deque
from typing import Generator, Optional
from pathlib import Path


class StreamingLogManager:
    """ストリーミングログ管理クラス"""

    def __init__(self, max_lines: int = 1000):
        """
        Args:
            max_lines: 保持する最大行数
        """
        self.max_lines = max_lines
        self.output_buffer: deque = deque(maxlen=max_lines)
        self.is_active = False
        self.current_status = "準備完了"
        self.lock = threading.Lock()

    def clear_buffer(self) -> None:
        """バッファをクリア"""
        with self.lock:
            self.output_buffer.clear()

    def add_line(self, line: str) -> None:
        """ログ行を追加

        Args:
            line: 追加するログ行
        """
        with self.lock:
            timestamp = time.strftime("%H:%M:%S")
            formatted_line = f"[{timestamp}] {line}"
            self.output_buffer.append(formatted_line)

    def add_status_line(self, message: str, status_type: str = "info") -> None:
        """ステータス行を追加

        Args:
            message: ステータスメッセージ
            status_type: ステータスタイプ (info, success, error, warning)
        """
        symbols = {
            "info": "ℹ️",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "start": "🚀",
            "complete": "🎉",
        }

        symbol = symbols.get(status_type, "ℹ️")
        self.add_line(f"{symbol} {message}")

        # 現在のステータスを更新
        with self.lock:
            self.current_status = message

    def get_current_output(self) -> str:
        """現在のログ出力を取得

        Returns:
            フォーマットされたログ出力
        """
        with self.lock:
            if not self.output_buffer:
                return "準備完了"

            return "\n".join(self.output_buffer)

    def get_status(self) -> str:
        """現在のステータスを取得

        Returns:
            現在のステータス
        """
        with self.lock:
            return self.current_status

    def set_active(self, active: bool) -> None:
        """アクティブ状態を設定

        Args:
            active: アクティブ状態
        """
        with self.lock:
            self.is_active = active

    def is_running(self) -> bool:
        """実行中かどうかを確認

        Returns:
            実行中の場合True
        """
        with self.lock:
            return self.is_active

    def stream_generator(
        self, initial_message: str = "処理を開始しています..."
    ) -> Generator[str, None, None]:
        """ストリーミング用ジェネレータ

        Args:
            initial_message: 初期メッセージ

        Yields:
            現在のログ出力
        """
        self.clear_buffer()
        self.add_status_line(initial_message, "start")
        self.set_active(True)

        try:
            yield self.get_current_output()

            # 実行中は定期的にログを出力
            while self.is_running():
                current = self.get_current_output()
                yield current
                time.sleep(0.1)  # 100ms間隔で更新

        finally:
            self.set_active(False)


class LogFileMonitor:
    """ログファイル監視クラス"""

    def __init__(self, log_manager: StreamingLogManager):
        """
        Args:
            log_manager: ログマネージャー
        """
        self.log_manager = log_manager
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.current_file: Optional[Path] = None
        self.last_position = 0

    def start_monitoring(self, log_file_path: Path) -> None:
        """ログファイル監視を開始

        Args:
            log_file_path: 監視するログファイルのパス
        """
        self.stop_monitoring()

        self.current_file = log_file_path
        self.last_position = 0
        self.monitoring = True

        # ファイルが既に存在する場合、末尾から開始
        if log_file_path.exists():
            self.last_position = log_file_path.stat().st_size

        self.monitor_thread = threading.Thread(target=self._monitor_file, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        """ログファイル監視を停止"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def _monitor_file(self) -> None:
        """ログファイル監視の内部処理"""
        while self.monitoring and self.current_file:
            try:
                if not self.current_file.exists():
                    time.sleep(0.1)
                    continue

                current_size = self.current_file.stat().st_size

                if current_size > self.last_position:
                    # ファイルに新しい内容がある場合
                    with open(
                        self.current_file, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        f.seek(self.last_position)
                        new_lines = f.readlines()

                        for line in new_lines:
                            line = line.rstrip()
                            if line:  # 空行でない場合のみ追加
                                self.log_manager.add_line(line)

                    self.last_position = current_size

                time.sleep(0.1)  # 100ms間隔でチェック

            except Exception as e:
                self.log_manager.add_status_line(
                    f"ログファイル監視エラー: {e}", "error"
                )
                time.sleep(1.0)  # エラー時は少し長めに待機


# グローバルインスタンス
log_manager = StreamingLogManager()
file_monitor = LogFileMonitor(log_manager)
