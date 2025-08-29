"""
実行管理マネージャー
"""

import threading
import time
from typing import Optional

from apps.queue.components.core.queue_manager import get_queue_manager
from apps.queue.components.core.slack_notifier import get_slack_notifier
from apps.queue.components.core.task_executor import get_task_executor


class ExecutorManager:
    """キュー実行管理"""

    def __init__(self):
        self.queue_manager = get_queue_manager()
        self.task_executor = get_task_executor()
        self.slack = get_slack_notifier()

        self._execution_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._pause_flag = threading.Event()

    def start_queue(self) -> bool:
        """キュー処理を開始"""
        if self.is_running():
            return False

        self._stop_flag.clear()
        self._pause_flag.clear()

        # キューサイズを取得
        queue_size = len(self.queue_manager.state.pending_tasks)
        if queue_size == 0:
            return False

        # Slack通知（キュー開始）
        self.slack.notify_queue_start(queue_size)

        # 実行スレッド開始
        self._execution_thread = threading.Thread(
            target=self._execution_loop, daemon=True
        )
        self._execution_thread.start()

        self.queue_manager.state.is_running = True
        return True

    def stop_queue(self) -> None:
        """キュー処理を停止"""
        self._stop_flag.set()

        # 実行中のタスクを停止
        self.task_executor.stop_execution()

        # スレッド終了を待機
        if self._execution_thread and self._execution_thread.is_alive():
            self._execution_thread.join(timeout=5)

        self.queue_manager.state.is_running = False

    def pause_queue(self) -> None:
        """キュー処理を一時停止"""
        self._pause_flag.set()
        self.queue_manager.state.is_paused = True

    def resume_queue(self) -> None:
        """キュー処理を再開"""
        self._pause_flag.clear()
        self.queue_manager.state.is_paused = False

    def is_running(self) -> bool:
        """実行中か判定"""
        return self._execution_thread is not None and self._execution_thread.is_alive()

    def is_paused(self) -> bool:
        """一時停止中か判定"""
        return self._pause_flag.is_set()

    def _execution_loop(self) -> None:
        """実行ループ"""
        initial_queue_size = len(self.queue_manager.state.pending_tasks)
        start_time = time.time()

        try:
            while not self._stop_flag.is_set():
                # 一時停止チェック
                while self._pause_flag.is_set():
                    if self._stop_flag.is_set():
                        return
                    time.sleep(1)

                # 次のタスクを取得
                task = self.queue_manager.get_next_task()
                if not task:
                    break  # キューが空

                # タスク実行
                success, error_msg = self.task_executor.execute_task(task)

                # タスク完了処理
                self.queue_manager.complete_task(task.id, success, error_msg)

                # Slack通知（タスク完了）
                # 注意: 100%進捗通知でnotify_on_completeが有効な場合は
                # 統合通知が既に送信されているため、重複を避ける
                if task.execution_time:
                    should_send_complete = True
                    
                    # 成功時かつ進捗通知が有効かつ完了通知が有効な場合は統合通知済み
                    if (success and 
                        self.slack.config.notify_progress and 
                        self.slack.config.notify_on_complete):
                        should_send_complete = False
                    
                    if should_send_complete:
                        self.slack.notify_task_complete(
                            task.id,
                            task.preset_name,
                            task.execution_time,
                            success,
                            error_msg,
                        )

                # 停止チェック
                if self._stop_flag.is_set():
                    break

            # キュー処理完了
            if not self._stop_flag.is_set():
                self._notify_queue_complete(initial_queue_size, start_time)

        finally:
            self.queue_manager.state.is_running = False
            self.queue_manager.state.is_paused = False

    def _notify_queue_complete(self, initial_size: int, start_time: float) -> None:
        """キュー完了通知"""
        stats = self.queue_manager._calculate_stats()
        total_time = time.time() - start_time

        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        time_str = f"{hours}時間{minutes}分"

        self.slack.notify_queue_complete(initial_size, time_str, stats["success_rate"])


# グローバルインスタンス管理
_executor_manager_instance: Optional[ExecutorManager] = None


def get_executor_manager() -> ExecutorManager:
    """シングルトンインスタンスを取得"""
    global _executor_manager_instance
    if _executor_manager_instance is None:
        _executor_manager_instance = ExecutorManager()
    return _executor_manager_instance
