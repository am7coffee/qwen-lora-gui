"""
学習進捗監視モジュール
"""

import re
import time
from pathlib import Path
from typing import Optional, Set
from apps.queue.components.core.slack_notifier import SlackNotifier
from apps.queue.components.core.gpu_monitor import (
    get_gpu_info,
    format_gpu_info_for_slack,
)


class ProgressMonitor:
    """学習進捗を監視してSlack通知を送信"""

    def __init__(
        self,
        log_file: Path,
        task_id: str,
        task_name: str,
        interval: int,
        slack_notifier: SlackNotifier,
    ):
        """
        Args:
            log_file: 監視するログファイル
            task_id: タスクID
            task_name: タスク名（プリセット名）
            interval: 通知間隔（%）
            slack_notifier: Slack通知インスタンス
        """
        self.log_file = log_file
        self.task_id = task_id
        self.task_name = task_name
        self.interval = interval
        self.slack = slack_notifier
        self.notified_percentages: Set[int] = set()
        self.monitoring = True
        self.last_position = 0
        self._initialize_file_position()

    def monitor_progress(self) -> None:
        """ログファイルを監視して進捗を通知"""
        # 正規表現パターン（100%時の00:00形式に対応）
        # steps:  20%|##        | 16/80 [00:34<02:18,  2.16s/it, avr_loss=0.125]
        # steps: 100%|██████████| 80/80 [02:40<00:00,  2.01s/it, avr_loss=0.113]
        pattern = re.compile(
            r"steps:\s+(\d+)%\|[^|]*\|\s+(\d+)/(\d+)\s+\[([^<]+)<([^,\]]+),?\s*([^,\]]+),?\s*avr_loss=([\d.]+)\]"
        )

        # プロセスが起動して最初の出力が始まるまで少し待つ
        time.sleep(3)

        while self.monitoring:
            if not self.log_file.exists():
                time.sleep(5)
                continue

            try:
                with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                    # 前回読んだ位置から開始
                    f.seek(self.last_position)
                    new_lines = f.readlines()
                    self.last_position = f.tell()  # 現在位置を記録

                    for line in new_lines:
                        match = pattern.search(line)
                        if match:
                            percentage = int(match.group(1))
                            current_step = match.group(2)
                            total_steps = match.group(3)
                            elapsed = match.group(4)
                            remaining = match.group(5)
                            speed = match.group(6)
                            avg_loss = match.group(7)

                            # 通知すべき進捗かチェック（100%も含む）
                            notification_threshold = self._get_notification_threshold(
                                percentage
                            )
                            if notification_threshold is not None:
                                # グラフ部分を除去してメッセージを整形
                                clean_msg = (
                                    f"steps: {percentage}%| {current_step}/{total_steps} "
                                    f"[{elapsed}<{remaining}, {speed}, avr_loss={avg_loss}]"
                                )
                                self._send_notification(
                                    notification_threshold, clean_msg
                                )

            except Exception as e:
                print(f"Progress monitoring error: {e}")

            time.sleep(5)  # 5秒ごとにチェック

    def _get_notification_threshold(self, percentage: int) -> Optional[int]:
        """通知すべき閾値を取得（None = 通知不要）"""
        # 100%超は通知しない
        if percentage > 100:
            return None

        # 100%の場合も通知対象
        if percentage == 100 and 100 not in self.notified_percentages:
            self.notified_percentages.add(100)
            return 100

        # 閾値計算（例：25%間隔なら 25, 50, 75）
        # percentageが到達または超えた閾値をチェック
        for threshold in range(self.interval, 100, self.interval):
            if percentage >= threshold and threshold not in self.notified_percentages:
                # この閾値に到達し、まだ通知していない
                self.notified_percentages.add(threshold)
                # 実際の通知はthresholdの値を使用
                return threshold

        return None

    def _send_notification(self, percentage: int, details: str) -> None:
        """Slack通知を送信"""
        # GPU情報を取得（有効な場合）
        gpu_info_text = None
        if self.slack.config.include_gpu_info:
            gpu_info = get_gpu_info()
            if gpu_info:
                gpu_info_text = format_gpu_info_for_slack(gpu_info)

        # 100%進捗の場合は統合通知を検討
        if percentage == 100 and self.slack.config.notify_on_complete:
            # 統合通知: 100%進捗 + タスク完了情報
            self.slack.notify_task_complete_with_progress(
                self.task_id, self.task_name, percentage, details, gpu_info_text
            )
        else:
            # 通常の進捗通知
            self.slack.notify_training_progress(
                self.task_id, self.task_name, percentage, details, gpu_info_text
            )

    def _initialize_file_position(self) -> None:
        """ファイル位置を初期化（ファイルの先頭から開始）"""
        # 常に先頭から開始して全ての進捗を確実にキャッチ
        self.last_position = 0

    def stop_monitoring(self) -> None:
        """監視を停止"""
        self.monitoring = False
