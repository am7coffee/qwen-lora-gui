"""
キューシステムメインアプリケーション
"""

import gradio as gr

from apps.queue.components.ui.components import (
    create_control_panel,
    create_queue_view,
    create_slack_settings,
    create_stats_panel,
)
from apps.queue.components.ui.handlers import QueueHandlers


class QueueSystemApp:
    """キューシステムGUIアプリケーション"""

    def __init__(self):
        self.handlers = QueueHandlers()
        self.interface = None

    def create_interface(self) -> gr.Blocks:
        """インターフェースを作成"""
        # キューシステム専用CSS
        queue_css = """
        /* キューに追加ボタン + Slack保存ボタン - オレンジ色 */
        #queue-add-btn, #queue-import-btn, #slack-save-btn {
            background-color: #f97316 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease-in-out !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        #queue-add-btn:hover, #queue-import-btn:hover, #slack-save-btn:hover {
            background-color: #ea580c !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        }
        
        #queue-add-btn:active, #queue-import-btn:active, #slack-save-btn:active {
            background-color: #c2410c !important;
            transform: translateY(0) !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        #queue-add-btn:focus, #queue-import-btn:focus, #slack-save-btn:focus {
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.3) !important;
        }
        
        /* タスク削除ボタン - 赤色 */
        #queue-delete-btn, #queue-clear-pending-btn {
            background-color: #dc2626 !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease-in-out !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        #queue-delete-btn:hover, #queue-clear-pending-btn:hover {
            background-color: #b91c1c !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        }
        
        #queue-delete-btn:active, #queue-clear-pending-btn:active {
            background-color: #991b1b !important;
            transform: translateY(0) !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        #queue-delete-btn:focus, #queue-clear-pending-btn:focus {
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.3) !important;
        }
        
        /* キュー開始ボタン - 修正された参考CSSの緑色を使用 */
        button#queue-start-btn, 
        .gradio-button#queue-start-btn,
        [id="queue-start-btn"] {
            background-color: #10b981 !important;
            background-image: none !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 8px 16px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease-in-out !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
            cursor: pointer !important;
        }
        
        button#queue-start-btn:hover, 
        .gradio-button#queue-start-btn:hover,
        [id="queue-start-btn"]:hover {
            background-color: #059669 !important;
            background-image: none !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        }
        
        button#queue-start-btn:active, 
        .gradio-button#queue-start-btn:active,
        [id="queue-start-btn"]:active {
            background-color: #047857 !important;
            background-image: none !important;
            transform: translateY(0) !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
        }
        
        button#queue-start-btn:focus, 
        .gradio-button#queue-start-btn:focus,
        [id="queue-start-btn"]:focus {
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.3) !important;
        }
        
        """

        with gr.Blocks(
            title="Queue System - Qwen LoRA GUI", css=queue_css, theme=gr.themes.Soft()
        ) as interface:
            gr.Markdown("# 🚀 キューシステム")

            with gr.Tabs():
                # キュー管理タブ
                with gr.Tab("📋 キュー管理"):
                    with gr.Row():
                        # 左側：コントロールパネル
                        with gr.Column(scale=1):
                            control_components = create_control_panel()
                            self._setup_control_handlers(control_components)

                        # 右側：キュー表示
                        with gr.Column(scale=3):
                            queue_components = create_queue_view()
                            # refresh_triggerをqueue_componentsに追加
                            queue_components["refresh_trigger"] = control_components[
                                "refresh_trigger"
                            ]
                    # 統計パネル
                    stats_components = create_stats_panel()

                    # ハンドラー設定（統計パネル情報を渡す）
                    self._setup_queue_handlers(queue_components, stats_components)
                    self._setup_stats_handlers(stats_components)

                # Slack設定タブ
                with gr.Tab("🔔 Slack設定"):
                    slack_components = create_slack_settings()
                    self._setup_slack_handlers(slack_components)

            # 定期更新設定
            self._setup_auto_refresh(queue_components, stats_components)

            # 初期データ表示とプリセット一覧の設定
            def initialize():
                # プリセット一覧を取得
                preset_list = self.handlers.get_preset_list()
                # 表示データを取得
                pending_df, running_df, completed_df, stats_text = (
                    self.handlers.refresh_display()
                )
                # Slack設定を取得
                slack_config = self.handlers.slack.config
                # Dropdownの更新方法を変更
                return (
                    gr.Dropdown(choices=preset_list, value=None),
                    pending_df,
                    running_df,
                    completed_df,
                    stats_text,
                    slack_config.enabled,
                    slack_config.webhook_url,
                    slack_config.notify_on_start,
                    slack_config.notify_on_complete,
                    slack_config.notify_on_error,
                    slack_config.notify_on_queue_start,
                    slack_config.notify_on_queue_complete,
                    slack_config.notify_progress,
                    slack_config.progress_interval,
                    slack_config.include_gpu_info,
                    gr.update(
                        visible=slack_config.notify_progress
                    ),  # ドロップダウンの表示状態
                    gr.update(
                        visible=slack_config.notify_progress
                    ),  # GPU情報チェックボックスの表示状態
                )

            interface.load(
                initialize,
                outputs=[
                    control_components["preset_dropdown"],
                    queue_components["pending_table"],
                    queue_components["running_table"],
                    queue_components["completed_table"],
                    stats_components["stats_display"],
                    slack_components["slack_enabled"],
                    slack_components["webhook_url"],
                    slack_components["notify_start"],
                    slack_components["notify_complete"],
                    slack_components["notify_error"],
                    slack_components["notify_queue_start"],
                    slack_components["notify_queue_complete"],
                    slack_components["notify_progress"],
                    slack_components["progress_interval"],
                    slack_components["include_gpu_info"],
                    slack_components["progress_interval"],  # 表示状態更新用
                    slack_components["include_gpu_info"],  # 表示状態更新用
                ],
            )

            # 定期自動更新の設定（3秒ごと）
            # Gradio 5.xのTimerコンポーネントを使用
            if hasattr(self, "auto_refresh_outputs"):
                # 3秒間隔のタイマーを作成
                timer = gr.Timer(value=3)

                # タイマーのtickイベントで更新（チェックボックスの状態を考慮）
                timer.tick(
                    fn=self.handlers.conditional_refresh_display,
                    inputs=[queue_components["auto_refresh_checkbox"]],
                    outputs=self.auto_refresh_outputs,
                )

        self.interface = interface
        return interface

    def _setup_control_handlers(self, components):
        """コントロールパネルのハンドラー設定"""
        # プリセット選択
        components["preset_dropdown"].change(
            self.handlers.on_preset_select,
            inputs=[components["preset_dropdown"]],
            outputs=[components["task_checkboxes"], components["output_preview"]],
        )

        # プリセットリスト再読み込み
        components["refresh_preset_button"].click(
            self.handlers.refresh_preset_list,
            outputs=[components["preset_dropdown"], components["add_result"]],
        )

        # タスクタイプ変更時
        components["task_checkboxes"].change(
            self.handlers.on_task_type_change,
            inputs=[components["task_checkboxes"]],
            outputs=[components["output_preview"]],
        )

        # プリセットファイルインポート（ボタンクリック時）
        components["import_button"].click(
            self.handlers.import_preset_files,
            inputs=[components["preset_file_upload"], components["import_task_types"]],
            outputs=[components["import_result"], components["refresh_trigger"]],
        )

        # タスク追加
        components["add_button"].click(
            self.handlers.add_to_queue,
            inputs=[components["preset_dropdown"], components["task_checkboxes"]],
            outputs=[components["add_result"], components["refresh_trigger"]],
        )

    def _setup_queue_handlers(self, components, stats_components):
        """キュー表示のハンドラー設定"""
        # 自動更新チェックボックス
        components["auto_refresh_checkbox"].change(
            self.handlers.toggle_auto_refresh,
            inputs=[components["auto_refresh_checkbox"]],
            outputs=[components["manual_refresh_button"]],
        )

        # 手動更新ボタン
        refresh_components = [
            components["pending_table"],
            components["running_table"],
            components["completed_table"],
            stats_components["stats_display"],
        ]
        components["manual_refresh_button"].click(
            self.handlers.refresh_display,
            outputs=refresh_components,
        )

        # キュー制御
        components["start_button"].click(
            self.handlers.start_queue,
            outputs=[components["queue_status"], components["refresh_trigger"]],
        )

        components["stop_button"].click(
            self.handlers.stop_queue,
            outputs=[components["queue_status"], components["refresh_trigger"]],
        )

        components["pause_button"].click(
            self.handlers.toggle_pause,
            outputs=[components["queue_status"], components["refresh_trigger"]],
        )

        # 削除ボタン（selectイベントをスキップして、削除時に直接入力）
        components["delete_button"].click(
            self.handlers.delete_task,
            inputs=[components["delete_task_id"]],
            outputs=[components["delete_result"], components["refresh_trigger"]],
        )

        # 未実行タスク一括削除
        components["clear_pending_button"].click(
            self.handlers.clear_pending,
            outputs=[components["delete_result"], components["refresh_trigger"]],
        )

        # 完了タスククリア
        components["clear_completed_button"].click(
            self.handlers.clear_completed,
            outputs=[components["clear_result"], components["refresh_trigger"]],
        )

    def _setup_stats_handlers(self, components):
        """統計パネルのハンドラー設定"""
        # ログ表示
        components["view_log_button"].click(
            self.handlers.view_log,
            inputs=[components["log_task_id"]],
            outputs=[components["log_viewer"]],
        )

    def _setup_slack_handlers(self, components):
        """Slack設定のハンドラー設定"""
        # 設定保存
        components["save_slack_button"].click(
            self.handlers.save_slack_config,
            inputs=[
                components["slack_enabled"],
                components["webhook_url"],
                components["notify_start"],
                components["notify_complete"],
                components["notify_error"],
                components["notify_queue_start"],
                components["notify_queue_complete"],
                components["notify_progress"],
                components["progress_interval"],
                components["include_gpu_info"],
            ],
            outputs=[components["slack_save_result"]],
        )

        # 進捗通知チェックボックスの変更でドロップダウンとGPU情報チェックボックスの表示を切り替え
        components["notify_progress"].change(
            fn=lambda checked: (gr.update(visible=checked), gr.update(visible=checked)),
            inputs=[components["notify_progress"]],
            outputs=[components["progress_interval"], components["include_gpu_info"]],
        )

        # テスト送信
        components["test_slack_button"].click(
            self.handlers.test_slack,
            inputs=[components["webhook_url"]],
            outputs=[components["slack_test_result"]],
        )

    def _setup_auto_refresh(self, queue_components, stats_components):
        """自動更新の設定"""
        # 更新対象のコンポーネント
        refresh_components = [
            queue_components["pending_table"],
            queue_components["running_table"],
            queue_components["completed_table"],
            stats_components["stats_display"],
        ]

        # 手動更新トリガー（従来の機能を維持）
        queue_components["refresh_trigger"].change(
            self.handlers.refresh_display, outputs=refresh_components
        )

        # 定期自動更新の設定（3秒ごと）
        # デモ（Blocks）のloadイベントで設定する必要がある
        # ここでは設定を保存しておき、create_interfaceメソッド内で適用
        self.auto_refresh_outputs = refresh_components
        self.auto_refresh_interval = 3

    def launch(self, **kwargs):
        """アプリケーションを起動"""
        if not self.interface:
            self.create_interface()
        return self.interface.launch(**kwargs)
