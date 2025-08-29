"""
UIイベントハンドラー
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import pandas as pd

from apps.queue.components.core.executor_manager import get_executor_manager
from apps.queue.components.core.queue_manager import get_queue_manager
from apps.queue.components.core.slack_notifier import get_slack_notifier


class QueueHandlers:
    """キューシステムのイベントハンドラー"""

    def __init__(self):
        self.queue_manager = get_queue_manager()
        self.executor_manager = get_executor_manager()
        self.slack = get_slack_notifier()
        self.preset_dir = Path("data/presets")
        self.refresh_counter = 0  # リフレッシュカウンター
        self.auto_refresh_enabled = True  # 自動更新の状態

    # === プリセット関連 ===

    def on_preset_select(self, preset_name: str) -> Tuple[gr.CheckboxGroup, str]:
        """プリセット選択時の処理"""
        # デフォルト値
        default_tasks = ["training"]
        default_output = "未設定"

        if not preset_name:
            return gr.CheckboxGroup(value=default_tasks), default_output

        preset_path = self.preset_dir / f"{preset_name}.json"
        if not preset_path.exists():
            return gr.CheckboxGroup(
                value=default_tasks
            ), "プリセットファイルが見つかりません"

        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                preset_data = json.load(f)

            # 出力先情報を取得
            params = preset_data.get("parameters", {})
            output_dir = self._extract_param(params, "output_dir")
            output_name = self._extract_param(params, "output_name")

            output_text = default_output
            if output_dir and output_name:
                output_text = f"{output_dir}/{output_name}"
            elif output_dir:
                output_text = f"{output_dir}/（名前未設定）"
            elif output_name:
                output_text = f"（フォルダ未設定）/{output_name}"

            # プリセット情報を保存（タスク変更時に使用）
            self.current_preset_output = {"dir": output_dir, "name": output_name}
            return gr.CheckboxGroup(value=default_tasks), output_text

        except Exception as e:
            print(f"プリセット読み込みエラー: {e}")
            return gr.CheckboxGroup(value=default_tasks), "読み込みエラー"

    def on_task_type_change(self, task_types: List[str]) -> str:
        """タスクタイプ変更時の処理"""
        # 学習実行が含まれていない場合
        if "training" not in task_types:
            return "（キャッシュのみ - モデル出力なし）"

        # プリセット情報がある場合
        if hasattr(self, "current_preset_output"):
            output_dir = self.current_preset_output.get("dir")
            output_name = self.current_preset_output.get("name")

            if output_dir and output_name:
                return f"{output_dir}/{output_name}"
            elif output_dir:
                return f"{output_dir}/（名前未設定）"
            elif output_name:
                return f"（フォルダ未設定）/{output_name}"

        return "未設定"

    # === キュー操作 ===

    def add_to_queue(self, preset_name: str, task_types: List[str]) -> Tuple[str, int]:
        """タスクをキューに追加"""
        if not preset_name:
            return "❌ プリセットを選択してください", 0

        if not task_types:
            return "❌ 実行タスクを選択してください", 0

        preset_path = str(self.preset_dir / f"{preset_name}.json")
        result = self.queue_manager.add_task(preset_path, task_types)

        if result["success"]:
            msg = f"✅ タスクを追加しました (ID: {result['task_id']}, 位置: {result['position']})"
            if result["warnings"]:
                msg += "\n" + "\n".join(result["warnings"])
            self.refresh_counter += 1
            return msg, self.refresh_counter
        else:
            return "❌ タスクの追加に失敗しました", self.refresh_counter

    def delete_task(self, task_ids_input: str) -> Tuple[str, int]:
        """タスクを削除（複数ID対応）"""
        if not task_ids_input:
            return "❌ タスクが選択されていません", self.refresh_counter

        # 改行、スペース、カンマで分割してIDリストを作成
        task_ids = []
        for line in task_ids_input.replace(",", "\n").replace(" ", "\n").split("\n"):
            id_cleaned = line.strip()
            if id_cleaned:
                task_ids.append(id_cleaned)

        if not task_ids:
            return "❌ 有効なタスクIDが入力されていません", self.refresh_counter

        # 削除結果を記録
        deleted = []
        not_found = []

        for task_id in task_ids:
            if self.queue_manager.remove_task(task_id):
                deleted.append(task_id)
            else:
                not_found.append(task_id)

        # 結果メッセージを作成
        messages = []
        if deleted:
            self.refresh_counter += 1
            if len(deleted) == 1:
                messages.append(f"✅ タスク {deleted[0]} を削除しました")
            else:
                messages.append(
                    f"✅ {len(deleted)}件のタスクを削除しました: {', '.join(deleted)}"
                )

        if not_found:
            if len(not_found) == 1:
                messages.append(f"❌ タスク {not_found[0]} が見つかりません")
            else:
                messages.append(
                    f"❌ {len(not_found)}件のタスクが見つかりません: {', '.join(not_found)}"
                )

        return "\n".join(
            messages
        ) if messages else "❌ タスクの削除に失敗しました", self.refresh_counter

    def clear_completed(self) -> Tuple[str, int]:
        """完了タスクをクリア"""
        count = self.queue_manager.clear_completed()
        self.refresh_counter += 1
        return f"✅ {count}件の完了タスクをクリアしました", self.refresh_counter

    def clear_pending(self) -> Tuple[str, int]:
        """未実行タスクをすべて削除"""
        count = self.queue_manager.clear_pending()
        self.refresh_counter += 1
        return f"✅ {count}件の未実行タスクを削除しました", self.refresh_counter

    # === キュー制御 ===

    def start_queue(self) -> Tuple[str, int]:
        """キュー処理を開始"""
        if self.executor_manager.is_running():
            return "⚠️ すでに実行中です", self.refresh_counter

        if self.executor_manager.start_queue():
            self.refresh_counter += 1
            return "▶️ キュー処理を開始しました", self.refresh_counter
        else:
            return "❌ キューが空です", self.refresh_counter

    def stop_queue(self) -> Tuple[str, int]:
        """キュー処理を停止"""
        self.executor_manager.stop_queue()
        self.refresh_counter += 1
        return "⏹️ キュー処理を停止しました", self.refresh_counter

    def toggle_pause(self) -> Tuple[str, int]:
        """一時停止/再開を切り替え"""
        if self.executor_manager.is_paused():
            self.executor_manager.resume_queue()
            self.refresh_counter += 1
            return "▶️ キュー処理を再開しました", self.refresh_counter
        else:
            self.executor_manager.pause_queue()
            self.refresh_counter += 1
            return "⏸️ キュー処理を一時停止しました", self.refresh_counter

    # === 表示更新 ===

    def toggle_auto_refresh(self, checked: bool) -> Any:
        """自動更新のON/OFF切り替え"""
        self.auto_refresh_enabled = checked
        # 自動更新OFFの時のみ手動更新ボタンを表示
        return gr.update(visible=not checked)

    def conditional_refresh_display(
        self, auto_refresh_enabled: bool
    ) -> Tuple[Any, Any, Any, Any]:
        """条件付き表示更新（自動更新チェックボックスの状態を確認）"""
        if not auto_refresh_enabled:
            # 自動更新が無効の場合は現在のデータをそのまま返す
            return gr.update(), gr.update(), gr.update(), gr.update()

        return self.refresh_display()

    def refresh_display(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
        """表示を更新"""
        data = self.queue_manager.get_display_data()

        # DataFrameに変換
        pending_df = pd.DataFrame(
            data["pending"],
            columns=["No.", "ID", "プリセット", "タスク", "出力先"],
        )

        running_df = pd.DataFrame(
            data["running"],
            columns=["ID", "プリセット", "現在の処理", "開始時刻", "経過時間"],
        )

        completed_df = pd.DataFrame(
            data["completed"],
            columns=[
                "ID",
                "プリセット",
                "タスク",
                "状態",
                "開始",
                "完了",
                "実行時間",
                "備考",
            ],
        )

        # 統計情報
        stats = data["stats"]
        stats_text = f"""
        **処理済み:** {stats["total_completed"]}件
        **成功率:** {stats["success_rate"]:.1f}%
        **総実行時間:** {stats["total_time"]}
        """

        return pending_df, running_df, completed_df, stats_text

    def on_pending_select(self, evt: pd.DataFrame) -> str:
        """未実行タスク選択時の処理"""
        # DataFrameが渡される場合
        if isinstance(evt, pd.DataFrame):
            if not evt.empty:
                # 最初の行のID列を取得
                if "ID" in evt.columns:
                    return str(evt.iloc[0]["ID"])
                elif len(evt.columns) > 1:
                    return str(evt.iloc[0, 1])  # 2列目（ID列）
        return ""

    # === ログ表示 ===

    def view_log(self, task_id: str) -> str:
        """ログを表示"""
        if not task_id:
            return "タスクIDを入力してください"

        # ログファイルを検索
        log_dir = Path("data/queue_system/logs")
        if not log_dir.exists():
            return "ログディレクトリが存在しません"

        for log_file in log_dir.glob(f"{task_id}_*.log"):
            # エンコーディングを試行（UTF-8 → CP932 → エラー無視）
            encodings = ["utf-8", "cp932", "shift_jis"]
            for encoding in encodings:
                try:
                    with open(log_file, "r", encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            # 全てのエンコーディングで失敗した場合、エラーを無視して読み込み
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception as e:
                return f"ログ読み込みエラー: {e}"

        return f"タスク {task_id} のログが見つかりません"

    # === Slack設定 ===

    def save_slack_config(
        self,
        enabled: bool,
        webhook_url: str,
        notify_start: bool,
        notify_complete: bool,
        notify_error: bool,
        notify_queue_start: bool,
        notify_queue_complete: bool,
        notify_progress: bool,
        progress_interval: int,
        include_gpu_info: bool,
    ) -> str:
        """Slack設定を保存"""
        self.slack.update_config(
            enabled=enabled,
            webhook_url=webhook_url,
            notify_on_start=notify_start,
            notify_on_complete=notify_complete,
            notify_on_error=notify_error,
            notify_on_queue_start=notify_queue_start,
            notify_on_queue_complete=notify_queue_complete,
            notify_progress=notify_progress,
            progress_interval=progress_interval,
            include_gpu_info=include_gpu_info,
        )

        status = "有効" if enabled and webhook_url else "無効"
        return f"✅ Slack設定を保存しました (状態: {status})"

    def test_slack(self, webhook_url: str) -> str:
        """Slack接続をテスト"""
        if not webhook_url:
            return "❌ Webhook URLを入力してください"

        # 一時的にURLを設定してテスト
        original_url = self.slack.config.webhook_url
        self.slack.config.webhook_url = webhook_url

        result = self.slack.test_connection()

        # URLを戻す
        self.slack.config.webhook_url = original_url

        if result["success"]:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"

    # === ヘルパーメソッド ===

    def _extract_param(self, params: Dict[str, Any], key: str) -> Optional[str]:
        """パラメータから値を抽出"""
        if key in params:
            param_data = params[key]
            if isinstance(param_data, dict) and param_data.get("enabled"):
                value = param_data.get("value")
                return str(value) if value is not None else None
        return None

    def get_preset_list(self) -> List[str]:
        """プリセット一覧を取得"""
        if not self.preset_dir.exists():
            return []

        presets = []
        for preset_file in self.preset_dir.glob("*.json"):
            presets.append(preset_file.stem)

        return sorted(presets)

    def refresh_preset_list(self) -> Tuple[gr.Dropdown, str]:
        """プリセット一覧を再読み込み"""
        preset_list = self.get_preset_list()
        message = f"✅ プリセット一覧を再読み込みしました（{len(preset_list)}件）"
        return gr.Dropdown(choices=preset_list, value=None), message

    def import_preset_files(
        self, files: List, task_types: List[str]
    ) -> Tuple[str, int]:
        """プリセットファイルを直接インポートしてキューに追加"""
        if not files:
            return "❌ ファイルが選択されていません", 0

        if not task_types:
            return "❌ 実行タスクを選択してください", 0

        success_count = 0
        error_messages = []
        added_tasks = []

        for file in files:
            try:
                # ファイルパスを取得
                if hasattr(file, "name"):
                    file_path = file.name
                else:
                    file_path = str(file)

                # JSONファイルを検証（読み込みの確認のみ）
                with open(file_path, "r", encoding="utf-8") as f:
                    json.load(f)  # 有効なJSONか確認

                # プリセットの名前を取得（ファイル名から）
                preset_name = Path(file_path).stem

                # キューに追加
                result = self.queue_manager.add_task(file_path, task_types)

                if result["success"]:
                    success_count += 1
                    task_names = ", ".join(task_types)
                    added_tasks.append(
                        f"• {preset_name} (ID: {result['task_id']}, タスク: {task_names})"
                    )
                    if result["warnings"]:
                        for warning in result["warnings"]:
                            error_messages.append(f"⚠️ {preset_name}: {warning}")
                else:
                    error_messages.append(f"❌ {preset_name}: 追加失敗")

            except json.JSONDecodeError:
                error_messages.append(f"❌ {Path(file_path).name}: 無効なJSONファイル")
            except Exception as e:
                error_messages.append(f"❌ {Path(file_path).name}: {str(e)}")

        # 結果メッセージを作成
        if success_count > 0:
            msg = f"✅ {success_count}件のプリセットをキューに追加しました:\n"
            msg += "\n".join(added_tasks)
            if error_messages:
                msg += "\n\n" + "\n".join(error_messages)
            self.refresh_counter += 1
            return msg, self.refresh_counter
        else:
            msg = "❌ プリセットの追加に失敗しました"
            if error_messages:
                msg += "\n" + "\n".join(error_messages)
            return msg, self.refresh_counter
