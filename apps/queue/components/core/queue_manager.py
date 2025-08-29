"""
キュー管理の中核クラス
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.queue.components.core.models import QueueState, QueueTask, TaskType


class QueueManager:
    """キュー管理の中核クラス"""

    def __init__(self, state_file: str = "data/queue_system/queue_state.json"):
        self.state_file = Path(state_file)
        self.state = QueueState()
        self._lock = threading.Lock()
        self._load_state()

    # === 基本操作 ===

    def add_task(self, preset_path: str, task_types: List[str]) -> Dict[str, Any]:
        """タスクをキューに追加

        Args:
            preset_path: プリセットファイルパス
            task_types: 実行するタスクタイプのリスト

        Returns:
            {
                "success": bool,
                "task_id": str,
                "warnings": List[str],
                "position": int
            }
        """
        with self._lock:
            # タスク作成
            task = self._create_task(preset_path, task_types)

            # 重複チェック
            warnings = self._check_duplications(task)

            # キューに追加
            self.state.pending_tasks.append(task)
            self._save_state()

            return {
                "success": True,
                "task_id": task.id,
                "warnings": warnings,
                "position": len(self.state.pending_tasks),
            }

    def remove_task(self, task_id: str) -> bool:
        """未実行タスクを削除"""
        with self._lock:
            for i, task in enumerate(self.state.pending_tasks):
                if task.id == task_id:
                    del self.state.pending_tasks[i]
                    self._save_state()
                    return True
            return False

    def clear_completed(self) -> int:
        """完了済みタスクをクリア"""
        with self._lock:
            count = len(self.state.completed_tasks)
            self.state.completed_tasks.clear()
            self._save_state()
            return count

    def clear_pending(self) -> int:
        """未実行タスクをすべて削除"""
        with self._lock:
            count = len(self.state.pending_tasks)
            self.state.pending_tasks.clear()
            self._save_state()
            return count

    def get_next_task(self) -> Optional[QueueTask]:
        """次のタスクを取得して実行中に設定"""
        with self._lock:
            if not self.state.pending_tasks:
                return None

            task = self.state.pending_tasks.pop(0)
            task.status = "running"
            task.started_at = datetime.now()
            self.state.running_task = task
            self._save_state()
            return task

    def complete_task(
        self, task_id: str, success: bool, error_msg: Optional[str] = None
    ) -> None:
        """タスクを完了"""
        with self._lock:
            if self.state.running_task and self.state.running_task.id == task_id:
                task = self.state.running_task
                task.completed_at = datetime.now()
                task.status = "completed" if success else "failed"
                task.error_message = error_msg

                self.state.completed_tasks.append(task)
                self.state.running_task = None
                self._save_state()

    # === 重複チェック ===

    def _check_duplications(self, new_task: QueueTask) -> List[str]:
        """出力先の重複をチェック"""
        warnings: List[str] = []

        # 学習実行タスクが含まれていない場合は重複チェックをスキップ
        if "training" not in new_task.task_types:
            return warnings

        if not new_task.output_dir or not new_task.output_name:
            return warnings

        # 未実行キューとの重複チェック
        for task in self.state.pending_tasks:
            # 相手も学習実行タスクを含む場合のみチェック
            if "training" in task.task_types and self._is_duplicate_output(
                task, new_task
            ):
                warnings.append(
                    f"⚠️ キューID:{task.id} ({task.preset_name}) と出力先が重複: "
                    f"{new_task.output_path}"
                )

        # 実行中タスクとの重複チェック
        if self.state.running_task:
            # 実行中タスクも学習実行を含む場合のみチェック
            if (
                "training" in self.state.running_task.task_types
                and self._is_duplicate_output(self.state.running_task, new_task)
            ):
                warnings.append(f"⚠️ 実行中タスクと出力先が重複: {new_task.output_path}")

        return warnings

    def _is_duplicate_output(self, task1: QueueTask, task2: QueueTask) -> bool:
        """2つのタスクの出力先が重複しているか判定"""
        return (
            task1.output_dir == task2.output_dir
            and task1.output_name == task2.output_name
            and task1.output_dir is not None
            and task1.output_name is not None
        )

    # === 状態管理 ===

    def _save_state(self) -> None:
        """状態を永続化"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, indent=2, ensure_ascii=False)

    def _load_state(self) -> None:
        """状態を復元"""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 状態復元
            self.state.pending_tasks = [
                QueueTask.from_dict(t) for t in data.get("pending", [])
            ]
            self.state.completed_tasks = [
                QueueTask.from_dict(t) for t in data.get("completed", [])
            ]

            if data.get("running"):
                # 実行中タスクは未実行に戻す（クラッシュ対策）
                task = QueueTask.from_dict(data["running"])
                task.status = "pending"
                task.started_at = None
                self.state.pending_tasks.insert(0, task)

        except Exception as e:
            print(f"状態復元エラー: {e}")

    # === ヘルパーメソッド ===

    def _create_task(self, preset_path: str, task_types: List[str]) -> QueueTask:
        """タスクオブジェクトを作成"""
        # プリセット読み込み
        preset_data = self._load_preset(preset_path)

        task = QueueTask(
            preset_path=preset_path,
            preset_name=Path(preset_path).stem,
            preset_data=preset_data,
            task_types=self._sort_task_types(task_types),
        )

        # 出力先情報を抽出
        if preset_data:
            params = preset_data.get("parameters", {})
            task.output_dir = self._extract_param(params, "output_dir")
            task.output_name = self._extract_param(params, "output_name")

        return task

    def _sort_task_types(self, task_types: List[str]) -> List[str]:
        """タスクタイプを実行順序でソート"""
        order = TaskType.EXECUTION_ORDER
        return sorted(task_types, key=lambda x: order.index(x) if x in order else 999)

    def _extract_param(self, params: Dict[str, Any], key: str) -> Optional[str]:
        """パラメータから値を抽出"""
        if key in params:
            param_data = params[key]
            if isinstance(param_data, dict) and param_data.get("enabled"):
                value = param_data.get("value")
                return str(value) if value is not None else None
        return None

    def _load_preset(self, preset_path: str) -> Dict[str, Any]:
        """プリセットファイルを読み込み"""
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"プリセット読み込みエラー: {e}")
            return {}

    # === 表示用データ ===

    def get_display_data(self) -> Dict[str, Any]:
        """UI表示用データを取得"""
        with self._lock:
            return {
                "pending": self._format_pending_tasks(),
                "running": self._format_running_task(),
                "completed": self._format_completed_tasks(),
                "stats": self._calculate_stats(),
            }

    def _format_pending_tasks(self) -> List[List[Any]]:
        """未実行タスクを表示形式に変換"""
        rows = []
        for i, task in enumerate(self.state.pending_tasks):
            rows.append(
                [
                    i + 1,  # No.
                    task.id,
                    task.preset_name,
                    task.display_tasks,
                    task.output_path,
                ]
            )
        return rows

    def _format_running_task(self) -> List[List[Any]]:
        """実行中タスクを表示形式に変換"""
        if not self.state.running_task:
            return []

        task = self.state.running_task
        current_subtask = task.current_subtask
        current = (
            TaskType.DISPLAY_NAMES.get(current_subtask, "") if current_subtask else ""
        )

        return [
            [
                task.id,
                task.preset_name,
                current,
                task.started_at.strftime("%Y/%m/%d %H:%M:%S")
                if task.started_at
                else "",
                task.execution_time or "",
            ]
        ]

    def _format_completed_tasks(self) -> List[List[Any]]:
        """完了タスクを表示形式に変換"""
        rows = []
        for task in self.state.completed_tasks:
            rows.append(
                [
                    task.id,
                    task.preset_name,
                    task.display_tasks,
                    "✅" if task.status == "completed" else "❌",
                    task.started_at.strftime("%Y/%m/%d %H:%M:%S")
                    if task.started_at
                    else "",
                    task.completed_at.strftime("%Y/%m/%d %H:%M:%S")
                    if task.completed_at
                    else "",
                    task.execution_time or "",
                    task.error_message or "成功",
                ]
            )
        return rows

    def _calculate_stats(self) -> Dict[str, Any]:
        """統計情報を計算"""
        completed = len(self.state.completed_tasks)
        successful = sum(
            1 for t in self.state.completed_tasks if t.status == "completed"
        )

        total_seconds = 0.0
        for task in self.state.completed_tasks:
            if task.started_at and task.completed_at:
                delta = task.completed_at - task.started_at
                total_seconds += delta.total_seconds()

        return {
            "total_completed": completed,
            "success_rate": (successful / completed * 100) if completed > 0 else 0,
            "total_time": self._format_seconds(total_seconds),
        }

    def _format_seconds(self, seconds: float) -> str:
        """秒を時間文字列に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}時間{minutes}分"


# グローバルインスタンス管理
_queue_manager_instance: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """シングルトンインスタンスを取得"""
    global _queue_manager_instance
    if _queue_manager_instance is None:
        _queue_manager_instance = QueueManager()
    return _queue_manager_instance
