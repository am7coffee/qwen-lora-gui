"""
Slack通知機能
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests  # type: ignore


@dataclass
class SlackConfig:
    """Slack設定"""

    enabled: bool = False
    webhook_url: str = ""

    # 通知設定
    notify_on_start: bool = True
    notify_on_complete: bool = True
    notify_on_error: bool = True
    notify_on_queue_start: bool = True
    notify_on_queue_complete: bool = True

    # 学習進捗通知設定
    notify_progress: bool = False
    progress_interval: int = 25
    include_gpu_info: bool = False

    @classmethod
    def load_from_file(
        cls, config_file: str = "data/config/slack_config.json"
    ) -> "SlackConfig":
        """設定ファイルから読み込み"""
        config_path = Path(config_file)
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return cls(**data)
        except Exception:
            return cls()

    def save_to_file(self, config_file: str = "data/config/slack_config.json") -> None:
        """設定ファイルに保存"""
        config_path = Path(config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)


class SlackNotifier:
    """Slack通知クライアント"""

    def __init__(self):
        self.config = SlackConfig.load_from_file()
        self._session = requests.Session()

    def is_enabled(self) -> bool:
        """通知機能が有効か判定"""
        return self.config.enabled and bool(self.config.webhook_url)

    def update_config(
        self,
        enabled: Optional[bool] = None,
        webhook_url: Optional[str] = None,
        **kwargs,
    ) -> None:
        """設定を更新"""
        if enabled is not None:
            self.config.enabled = enabled
        if webhook_url is not None:
            self.config.webhook_url = webhook_url

        # その他の設定を更新
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        self.config.save_to_file()

    def test_connection(self) -> Dict[str, Any]:
        """接続テスト"""
        if not self.config.webhook_url:
            return {"success": False, "message": "WebhookURLが設定されていません"}

        try:
            message = {
                "text": "🔗 Slack接続テスト",
                "attachments": [
                    {
                        "color": "good",
                        "title": "接続テスト成功",
                        "text": "キューシステムからの通知が正常に送信できます。",
                        "footer": "Qwen LoRA GUI Queue System",
                        "ts": int(datetime.now().timestamp()),
                    }
                ],
            }

            response = self._send_message(message)

            if response.status_code == 200:
                return {"success": True, "message": "テスト送信成功"}
            else:
                return {
                    "success": False,
                    "message": f"送信失敗: HTTP {response.status_code}",
                }

        except Exception as e:
            return {"success": False, "message": f"エラー: {str(e)}"}

    def notify_task_start(self, task_id: str, preset_name: str, task_type: str) -> None:
        """タスク開始通知"""
        if not self.is_enabled() or not self.config.notify_on_start:
            return

        message = {
            "text": f"🚀 タスク開始: {preset_name}",
            "attachments": [
                {
                    "color": "#0080ff",
                    "fields": [
                        {"title": "タスクID", "value": task_id, "short": True},
                        {"title": "プリセット", "value": preset_name, "short": True},
                        {"title": "実行内容", "value": task_type, "short": False},
                    ],
                    "footer": "Qwen LoRA GUI Queue System",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        self._send_message_safe(message)

    def notify_task_complete(
        self,
        task_id: str,
        preset_name: str,
        execution_time: str,
        success: bool = True,
        error_msg: Optional[str] = None,
    ) -> None:
        """タスク完了通知"""
        if not self.is_enabled():
            return

        if success and not self.config.notify_on_complete:
            return
        if not success and not self.config.notify_on_error:
            return

        if success:
            message = {
                "text": f"✅ タスク完了: {preset_name}",
                "attachments": [
                    {
                        "color": "good",
                        "fields": [
                            {"title": "タスクID", "value": task_id, "short": True},
                            {
                                "title": "実行時間",
                                "value": execution_time,
                                "short": True,
                            },
                        ],
                        "footer": "Qwen LoRA GUI Queue System",
                        "ts": int(datetime.now().timestamp()),
                    }
                ],
            }
        else:
            message = {
                "text": f"❌ タスク失敗: {preset_name}",
                "attachments": [
                    {
                        "color": "danger",
                        "fields": [
                            {"title": "タスクID", "value": task_id, "short": True},
                            {
                                "title": "実行時間",
                                "value": execution_time,
                                "short": True,
                            },
                            {
                                "title": "エラー",
                                "value": error_msg or "不明なエラー",
                                "short": False,
                            },
                        ],
                        "footer": "Qwen LoRA GUI Queue System",
                        "ts": int(datetime.now().timestamp()),
                    }
                ],
            }

        self._send_message_safe(message)

    def notify_queue_start(self, queue_size: int) -> None:
        """キュー処理開始通知"""
        if not self.is_enabled() or not self.config.notify_on_queue_start:
            return

        message = {
            "text": "📋 キュー処理開始",
            "attachments": [
                {
                    "color": "#00ff00",
                    "fields": [
                        {
                            "title": "待機タスク数",
                            "value": str(queue_size),
                            "short": True,
                        },
                        {
                            "title": "開始時刻",
                            "value": datetime.now().strftime("%H:%M:%S"),
                            "short": True,
                        },
                    ],
                    "footer": "Qwen LoRA GUI Queue System",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        self._send_message_safe(message)

    def notify_queue_complete(
        self, total_tasks: int, total_time: str, success_rate: float
    ) -> None:
        """キュー処理完了通知"""
        if not self.is_enabled() or not self.config.notify_on_queue_complete:
            return

        message = {
            "text": "🎉 キュー処理完了",
            "attachments": [
                {
                    "color": "good",
                    "fields": [
                        {
                            "title": "処理タスク数",
                            "value": str(total_tasks),
                            "short": True,
                        },
                        {"title": "総実行時間", "value": total_time, "short": True},
                        {
                            "title": "成功率",
                            "value": f"{success_rate:.1f}%",
                            "short": True,
                        },
                        {
                            "title": "完了時刻",
                            "value": datetime.now().strftime("%H:%M:%S"),
                            "short": True,
                        },
                    ],
                    "footer": "Qwen LoRA GUI Queue System",
                    "ts": int(datetime.now().timestamp()),
                }
            ],
        }

        self._send_message_safe(message)

    def notify_training_progress(
        self,
        task_id: str,
        task_name: str,
        percentage: int,
        details: str,
        gpu_info: Optional[str] = None,
    ) -> None:
        """学習進捗を通知"""
        if not self.is_enabled() or not self.config.notify_progress:
            return

        # GPU情報を詳細に追加
        full_details = details
        if gpu_info and self.config.include_gpu_info:
            full_details += f"\n{gpu_info}"

        message = {
            "text": f"📊 学習進捗: {percentage}% - {task_name}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"学習進捗: {percentage}%",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*タスクID:*\n{task_id}"},
                        {"type": "mrkdwn", "text": f"*プリセット:*\n{task_name}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{full_details}```"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_Qwen LoRA GUI Queue System • {datetime.now().strftime('%H:%M:%S')}_",
                        }
                    ],
                },
            ],
        }

        self._send_message_safe(message)

    def notify_task_complete_with_progress(
        self,
        task_id: str,
        task_name: str,
        percentage: int,
        progress_details: str,
        gpu_info: Optional[str] = None,
        execution_time: Optional[str] = None,
    ) -> None:
        """タスク完了と100%進捗の統合通知"""
        if not self.is_enabled():
            return

        # GPU情報を詳細に追加
        full_details = progress_details
        if gpu_info and self.config.include_gpu_info:
            full_details += f"\n{gpu_info}"

        message = {
            "text": f"✅ タスク完了: {percentage}% - {task_name}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"✅ タスク完了: {percentage}%",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*タスクID:*\n{task_id}"},
                        {"type": "mrkdwn", "text": f"*プリセット:*\n{task_name}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{full_details}```"},
                },
            ],
        }
        
        # 実行時間が利用可能な場合は追加
        if execution_time:
            fields = message["blocks"][1]["fields"]  # type: ignore
            fields.append({  # type: ignore
                "type": "mrkdwn", 
                "text": f"*実行時間:*\n{execution_time}"
            })

        # フッター情報
        blocks = message["blocks"]  # type: ignore
        blocks.append({  # type: ignore
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Qwen LoRA GUI Queue System • {datetime.now().strftime('%H:%M:%S')}_",
                }
            ],
        })

        self._send_message_safe(message)

    def _send_message(self, message: Dict[str, Any]) -> requests.Response:
        """メッセージ送信（内部用）"""
        return self._session.post(
            self.config.webhook_url,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

    def _send_message_safe(self, message: Dict[str, Any]) -> None:
        """メッセージ送信（エラーハンドリング付き）"""
        try:
            self._send_message(message)
        except Exception as e:
            print(f"Slack通知エラー: {e}")


# グローバルインスタンス管理
_slack_notifier_instance: Optional[SlackNotifier] = None


def get_slack_notifier() -> SlackNotifier:
    """シングルトンインスタンスを取得"""
    global _slack_notifier_instance
    if _slack_notifier_instance is None:
        _slack_notifier_instance = SlackNotifier()
    return _slack_notifier_instance
