"""
UIコンポーネント定義
"""

from typing import Dict, Any

import gradio as gr


def create_control_panel() -> Dict[str, Any]:
    """コントロールパネルを作成"""
    components: Dict[str, Any] = {}

    with gr.Column():
        gr.Markdown("### 🎯 タスク追加")

        # 再読み込みボタン
        components["refresh_preset_button"] = gr.Button(
            "🔄 プリセットリスト再読み込み", variant="secondary", size="sm"
        )

        # プリセット選択
        components["preset_dropdown"] = gr.Dropdown(
            label="プリセット選択",
            choices=[],
            value=None,
            interactive=True,
            allow_custom_value=False,
        )

        # タスクタイプ選択
        components["task_checkboxes"] = gr.CheckboxGroup(
            label="実行タスク",
            choices=[
                ("潜在変数キャッシュ生成", "latent_cache"),
                ("TEキャッシュ生成", "te_cache"),
                ("学習実行", "training"),
            ],
            value=["training"],
            interactive=True,
        )

        # 出力先プレビュー
        components["output_preview"] = gr.Textbox(label="LoRA出力先", interactive=False)

        # 追加ボタン
        components["add_button"] = gr.Button(
            "📥 キューに追加", variant="primary", elem_id="queue-add-btn"
        )

        components["add_result"] = gr.Markdown("")

        # プリセットファイルインポート（セパレーター付き）
        gr.Markdown("---")
        gr.Markdown("#### 📁 プリセットファイル直接インポート")
        with gr.Row():
            components["preset_file_upload"] = gr.File(
                label="プリセットファイル（JSON）をドラッグ＆ドロップまたは選択",
                file_count="multiple",
                file_types=[".json"],
                interactive=True,
                scale=2,
            )
            components["import_task_types"] = gr.CheckboxGroup(
                label="インポート時の実行タスク",
                choices=[
                    ("潜在変数キャッシュ", "latent_cache"),
                    ("TEキャッシュ", "te_cache"),
                    ("学習", "training"),
                ],
                value=["training"],
                interactive=True,
                scale=1,
            )
        components["import_button"] = gr.Button(
            "📥 選択ファイルをキューに追加",
            variant="secondary",
            elem_id="queue-import-btn",
        )
        components["import_result"] = gr.Markdown("")

        # 更新トリガー（非表示）
        components["refresh_trigger"] = gr.Number(value=0, visible=False)

    return components


def create_queue_view() -> Dict[str, Any]:
    """キュー表示を作成"""
    components: Dict[str, Any] = {}

    with gr.Column():
        # キュー制御パネル（最上段）
        gr.Markdown("### 🎮 キュー制御")

        # 自動更新の制御
        with gr.Row():
            components["auto_refresh_checkbox"] = gr.Checkbox(
                label="🔄 自動更新（3秒間隔）", value=True, scale=1
            )
            components["manual_refresh_button"] = gr.Button(
                "🔄 手動更新", variant="secondary", size="sm", visible=False, scale=0
            )

        # キューステータス
        components["queue_status"] = gr.Markdown("⏸️ 停止中")

        # 制御ボタン
        with gr.Row():
            components["start_button"] = gr.Button(
                "▶️ 開始", variant="primary", elem_id="queue-start-btn"
            )
            components["pause_button"] = gr.Button("⏸️ 一時停止")
            components["stop_button"] = gr.Button("⏹️ 停止", variant="stop")

        gr.Markdown("---")

        # 実行中タスク（最優先表示）
        gr.Markdown("### ⚡ 実行中")
        components["running_table"] = gr.Dataframe(
            headers=["ID", "プリセット", "現在の処理", "開始時刻", "経過時間"],
            datatype=["str", "str", "str", "str", "str"],
            interactive=False,
            wrap=True,
        )

        # 未実行キュー
        with gr.Row():
            with gr.Column(scale=0, min_width=120):
                gr.Markdown("### 📋 未実行キュー")
            with gr.Column(scale=1, min_width=400):
                gr.Markdown("*ソート・フィルターは表示のみ（実行順は変わりません）*")
        components["pending_table"] = gr.Dataframe(
            headers=["No.", "ID", "プリセット", "タスク", "出力先"],
            datatype=["number", "str", "str", "str", "str"],
            interactive=False,
            wrap=True,
        )

        with gr.Row():
            components["delete_task_id"] = gr.Textbox(
                label="削除対象ID（複数可）",
                placeholder="削除したいタスクのIDを入力（改行・スペース・カンマ区切りで複数指定可）",
                scale=2,
                lines=3,
            )
            components["delete_button"] = gr.Button(
                "🗑️ タスクを削除", variant="stop", scale=1, elem_id="queue-delete-btn"
            )
            components["clear_pending_button"] = gr.Button(
                "🗑️ 未実行タスクを全削除",
                variant="stop",
                scale=1,
                elem_id="queue-clear-pending-btn",
            )
        components["delete_result"] = gr.Markdown("")

        # 完了タスク
        gr.Markdown("### ✅ 完了タスク")
        components["completed_table"] = gr.Dataframe(
            headers=[
                "ID",
                "プリセット",
                "タスク",
                "状態",
                "開始",
                "完了",
                "実行時間",
                "備考",
            ],
            column_widths=["100px", "20%", "20%", "60px", "15%", "15%", "80px", "15%"],
            datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
            interactive=False,
            wrap=True,
        )

        components["clear_completed_button"] = gr.Button("🧹 完了タスクをクリア")
        components["clear_result"] = gr.Markdown("")

    return components


def create_stats_panel() -> Dict[str, Any]:
    """統計パネルを作成"""
    components: Dict[str, Any] = {}

    with gr.Row():
        gr.Markdown("### 📊 統計情報")
        components["stats_display"] = gr.Markdown("")

    with gr.Row():
        components["log_task_id"] = gr.Textbox(
            label="タスクID（ログ表示）", placeholder="表示したいタスクのIDを入力"
        )
        components["view_log_button"] = gr.Button("📄 ログ表示")

    components["log_viewer"] = gr.Textbox(
        label="実行ログ", lines=20, max_lines=30, interactive=False
    )

    return components


def create_slack_settings() -> Dict[str, Any]:
    """Slack設定UIを作成"""
    components: Dict[str, Any] = {}

    with gr.Column():
        gr.Markdown("### 🔔 Slack通知設定")

        # マスタースイッチ
        components["slack_enabled"] = gr.Checkbox(
            label="Slack通知を有効にする", value=False
        )

        # Webhook URL
        components["webhook_url"] = gr.Textbox(
            label="Webhook URL",
            placeholder="https://hooks.slack.com/services/...",
            type="password",
        )

        with gr.Row():
            components["test_slack_button"] = gr.Button("📨 テスト送信")
            components["slack_test_result"] = gr.Markdown("")

        gr.Markdown("---")
        gr.Markdown("### 📢 通知タイミング")

        with gr.Row():
            with gr.Column():
                gr.Markdown("**タスク通知**")
                components["notify_start"] = gr.Checkbox(
                    label="タスク開始時", value=True
                )
                components["notify_complete"] = gr.Checkbox(
                    label="タスク完了時", value=True
                )
                components["notify_error"] = gr.Checkbox(
                    label="エラー発生時", value=True
                )

            with gr.Column():
                gr.Markdown("**キュー通知**")
                components["notify_queue_start"] = gr.Checkbox(
                    label="キュー開始時", value=True
                )
                components["notify_queue_complete"] = gr.Checkbox(
                    label="キュー完了時", value=True
                )

        # 学習進捗通知設定
        gr.Markdown("---")
        gr.Markdown("### 📊 学習進捗通知")
        with gr.Row():
            components["notify_progress"] = gr.Checkbox(
                label="学習途中経過を通知", value=False, scale=1
            )
            components["progress_interval"] = gr.Dropdown(
                label="進捗通知間隔",
                choices=[
                    ("10%ごと", 10),
                    ("20%ごと", 20),
                    ("25%ごと", 25),
                    ("50%ごと", 50),
                ],
                value=25,
                interactive=True,
                visible=False,  # 初期は非表示
                scale=1,
            )

        # GPU情報オプション
        with gr.Row():
            components["include_gpu_info"] = gr.Checkbox(
                label="GPU情報を含める（使用率・VRAM・温度）※GPU情報の通知はNvidia製GPUのみ対応",
                value=False,
                visible=False,  # 初期は非表示
                scale=1,
            )

        components["save_slack_button"] = gr.Button("💾 設定を保存", variant="primary", elem_id="slack-save-btn")
        components["slack_save_result"] = gr.Markdown("")

    return components
