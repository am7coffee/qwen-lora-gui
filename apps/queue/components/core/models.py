"""
データモデル定義
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class TaskType:
    """タスクタイプ定義"""

    LATENT_CACHE = "latent_cache"
    TE_CACHE = "te_cache"
    TRAINING = "training"

    # 表示名
    DISPLAY_NAMES = {
        LATENT_CACHE: "潜在変数キャッシュ生成",
        TE_CACHE: "TEキャッシュ生成",
        TRAINING: "学習実行",
    }

    # 実行順序
    EXECUTION_ORDER = [LATENT_CACHE, TE_CACHE, TRAINING]

    # コマンドタイプマッピング
    COMMAND_TYPES = {
        LATENT_CACHE: "latent",
        TE_CACHE: "text_encoder",
        TRAINING: "train",
    }


@dataclass
class QueueTask:
    """キュータスクモデル"""

    # 基本情報
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    preset_path: str = ""
    preset_name: str = ""
    preset_data: Dict[str, Any] = field(default_factory=dict)

    # タスク設定
    task_types: List[str] = field(default_factory=list)
    current_subtask_index: int = 0

    # 出力先情報
    output_dir: Optional[str] = None
    output_name: Optional[str] = None

    # ステータス
    status: str = "pending"  # pending, running, completed, failed, cancelled
    error_message: Optional[str] = None

    # タイムスタンプ
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 実行情報
    process_pid: Optional[int] = None
    log_file: Optional[str] = None

    @property
    def execution_time(self) -> Optional[str]:
        """実行時間を取得"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return self._format_timedelta(delta)
        elif self.started_at:
            delta = datetime.now() - self.started_at
            return f"{self._format_timedelta(delta)} (実行中)"
        return None

    @property
    def current_subtask(self) -> Optional[str]:
        """現在のサブタスクを取得"""
        if self.current_subtask_index < len(self.task_types):
            return self.task_types[self.current_subtask_index]
        return None

    @property
    def output_path(self) -> str:
        """出力パスを取得"""
        # 学習実行が含まれていない場合
        if "training" not in self.task_types:
            return "（キャッシュのみ）"

        if self.output_dir and self.output_name:
            return f"{self.output_dir}/{self.output_name}"
        return "未設定"

    @property
    def display_tasks(self) -> str:
        """タスクタイプを表示用文字列に変換"""
        return ", ".join([TaskType.DISPLAY_NAMES.get(t, t) for t in self.task_types])

    def _format_timedelta(self, delta: timedelta) -> str:
        """時間差を文字列にフォーマット"""
        total_seconds = int(delta.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}時間{minutes}分{seconds}秒"
        elif minutes > 0:
            return f"{minutes}分{seconds}秒"
        else:
            return f"{seconds}秒"

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（永続化用）"""
        return {
            "id": self.id,
            "preset_path": self.preset_path,
            "preset_name": self.preset_name,
            "task_types": self.task_types,
            "status": self.status,
            "output_dir": self.output_dir,
            "output_name": self.output_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error_message": self.error_message,
            "current_subtask_index": self.current_subtask_index,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueTask":
        """辞書から復元"""
        task = cls()
        for key, value in data.items():
            if key.endswith("_at") and value:
                setattr(task, key, datetime.fromisoformat(value))
            elif key == "preset_data":
                # preset_dataは保存しない（ファイルから再読み込み）
                continue
            else:
                setattr(task, key, value)
        return task

    def to_display_row(self, index: int = 0) -> List[Any]:
        """DataFrame表示用の行データを生成"""
        return [
            index,
            self.id,
            self.preset_name,
            self.display_tasks,
            self.output_path,
        ]


@dataclass
class QueueState:
    """キュー全体の状態"""

    pending_tasks: List[QueueTask] = field(default_factory=list)
    running_task: Optional[QueueTask] = None
    completed_tasks: List[QueueTask] = field(default_factory=list)
    is_running: bool = False
    is_paused: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """永続化用辞書"""
        return {
            "pending": [t.to_dict() for t in self.pending_tasks],
            "running": self.running_task.to_dict() if self.running_task else None,
            "completed": [t.to_dict() for t in self.completed_tasks],
            "is_running": self.is_running,
            "is_paused": self.is_paused,
        }


@dataclass
class DuplicationInfo:
    """重複情報"""

    task_id: str
    preset_name: str
    output_path: str
    conflicting_tasks: List[str] = field(default_factory=list)
    warning_level: str = "warning"  # info, warning, error
