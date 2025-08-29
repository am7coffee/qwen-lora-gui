"""
非同期タスク管理モジュール
バックグラウンドタスクの実行と監視を管理
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import logging


class TaskStatus(Enum):
    """タスク状態列挙型"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AsyncTask:
    """非同期タスク情報"""

    task_id: str
    task_type: str
    status: TaskStatus
    future: Optional[Future] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: float = 0.0
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class AsyncTaskManager:
    """非同期タスク管理クラス"""

    def __init__(self, max_workers: int = 4):
        """
        初期化

        Args:
            max_workers: スレッドプールの最大ワーカー数
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, AsyncTask] = {}
        self.lock = threading.RLock()

        # ログ設定
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

        # 定期清掃タスクを開始
        self._start_cleanup_task()

    def _setup_logging(self) -> None:
        """ログ設定"""
        log_dir = Path("data/logs/tasks")
        log_dir.mkdir(parents=True, exist_ok=True)

        handler = logging.FileHandler(log_dir / "task_manager.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def submit_task(
        self, task_id: str, task_type: str, func: Callable, *args, **kwargs
    ) -> AsyncTask:
        """タスクを投入

        Args:
            task_id: タスクID（一意）
            task_type: タスク種別
            func: 実行する関数
            *args: 関数の位置引数
            **kwargs: 関数のキーワード引数

        Returns:
            タスク情報
        """
        with self.lock:
            # 既存タスクをチェック
            if task_id in self.tasks:
                existing_task = self.tasks[task_id]
                if existing_task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    raise ValueError(f"Task {task_id} is already running")

            # タスク作成
            task = AsyncTask(
                task_id=task_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                created_at=time.time(),
            )

            # Futureを作成して投入
            try:
                future = self.executor.submit(
                    self._execute_task_wrapper, task, func, *args, **kwargs
                )
                task.future = future
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

                self.tasks[task_id] = task

                self.logger.info(f"Task {task_id} ({task_type}) submitted")
                return task

            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                self.tasks[task_id] = task

                self.logger.error(f"Failed to submit task {task_id}: {e}")
                raise e

    def _execute_task_wrapper(
        self, task: AsyncTask, func: Callable, *args, **kwargs
    ) -> Any:
        """タスク実行のラッパー

        Args:
            task: タスク情報
            func: 実行する関数
            *args: 関数の位置引数
            **kwargs: 関数のキーワード引数

        Returns:
            関数の実行結果
        """
        try:
            self.logger.info(f"Starting task {task.task_id}")

            result = func(*args, **kwargs)

            with self.lock:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = time.time()

            self.logger.info(f"Task {task.task_id} completed successfully")
            return result

        except Exception as e:
            with self.lock:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = time.time()

            self.logger.error(f"Task {task.task_id} failed: {e}")
            raise e

    def cancel_task(self, task_id: str) -> bool:
        """タスクをキャンセル

        Args:
            task_id: タスクID

        Returns:
            キャンセル成功の可否
        """
        with self.lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]

            if task.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ]:
                return False

            if task.future and task.future.cancel():
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()

                self.logger.info(f"Task {task_id} cancelled")
                return True

            return False

    def get_task_status(self, task_id: str) -> Optional[AsyncTask]:
        """タスク状態を取得

        Args:
            task_id: タスクID

        Returns:
            タスク情報（存在しない場合None）
        """
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]

                # Futureの状態を同期
                if task.future:
                    if task.future.done():
                        if task.status == TaskStatus.RUNNING:
                            if task.future.cancelled():
                                task.status = TaskStatus.CANCELLED
                            elif task.future.exception():
                                task.status = TaskStatus.FAILED
                                task.error = str(task.future.exception())
                            else:
                                task.status = TaskStatus.COMPLETED
                                task.result = task.future.result()

                            task.completed_at = time.time()

                return task

            return None

    def list_tasks(self, task_type: Optional[str] = None) -> Dict[str, AsyncTask]:
        """タスク一覧を取得

        Args:
            task_type: フィルタするタスク種別（省略時は全て）

        Returns:
            タスク一覧
        """
        with self.lock:
            if task_type:
                return {
                    task_id: task
                    for task_id, task in self.tasks.items()
                    if task.task_type == task_type
                }
            else:
                return self.tasks.copy()

    def wait_for_task(
        self, task_id: str, timeout: Optional[float] = None
    ) -> Optional[Any]:
        """タスク完了を待機

        Args:
            task_id: タスクID
            timeout: タイムアウト秒数

        Returns:
            タスク結果（タイムアウトまたはエラーの場合None）
        """
        task = self.get_task_status(task_id)
        if not task or not task.future:
            return None

        try:
            return task.future.result(timeout=timeout)
        except Exception as e:
            self.logger.error(f"Error waiting for task {task_id}: {e}")
            return None

    def cleanup_completed_tasks(self, max_age_hours: int = 24) -> int:
        """完了したタスクをクリーンアップ

        Args:
            max_age_hours: 保持する最大時間

        Returns:
            削除されたタスク数
        """
        cutoff_time = time.time() - (max_age_hours * 3600)

        with self.lock:
            to_remove = []

            for task_id, task in self.tasks.items():
                if (
                    task.status
                    in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                    and task.completed_at
                    and task.completed_at < cutoff_time
                ):
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]

            self.logger.info(f"Cleaned up {len(to_remove)} old tasks")
            return len(to_remove)

    def _start_cleanup_task(self) -> None:
        """定期清掃タスクを開始"""

        def cleanup_worker():
            while True:
                try:
                    self.cleanup_completed_tasks(max_age_hours=24)
                    time.sleep(3600)  # 1時間間隔
                except Exception as e:
                    self.logger.error(f"Cleanup task error: {e}")
                    time.sleep(600)  # エラー時は10分後にリトライ

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()

    def shutdown(self, wait: bool = True) -> None:
        """タスクマネージャーを終了

        Args:
            wait: 実行中タスクの完了を待つかどうか
        """
        self.logger.info("Shutting down task manager")
        self.executor.shutdown(wait=wait)


# グローバルインスタンス
async_task_manager = AsyncTaskManager()
