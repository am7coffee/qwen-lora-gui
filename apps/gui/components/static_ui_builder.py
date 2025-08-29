"""
静的UIビルダー
識別子ベースの管理を維持しながら、UIコンポーネントの配置を静的に行う
"""

import gradio as gr  # type: ignore
from typing import Any, Dict, List
from core.config.parameters import ParameterConfig
from core.validation.cli_file_validator import get_cli_file_validator


class StaticUIBuilder:
    """識別子ベースの静的UIビルダー（見た目を維持）"""

    def __init__(
        self,
        component_registry: Dict[str, Dict[str, Any]],
        parameters: Dict[str, ParameterConfig],
    ):
        """
        Args:
            component_registry: コンポーネントレジストリ
            parameters: パラメータ定義の辞書
        """
        self.registry = component_registry  # 既存のregistryを活用
        self.parameters = parameters  # parameters.pyから取得したパラメータ定義
        self.components: Dict[str, Any] = {}
        self.cli_validator = get_cli_file_validator()  # CLI環境ファイル検証

    def _register_component(
        self, elem_id: str, component: Any, param_name: str, role: str
    ) -> None:
        """コンポーネントをregistryに登録"""
        self.registry[elem_id] = {
            "component": component,
            "param_name": param_name,
            "role": role,
            "param_config": self.parameters.get(param_name),
        }

    def _validate_dit_realtime(self, file_path: str) -> Any:
        """--ditファイルパスのリアルタイム検証"""
        print(f"[DEBUG] _validate_dit_realtime called with: '{file_path}'")

        # 一時的なテスト：空でない場合は常にエラーとする
        if file_path and file_path.strip():
            print("[DEBUG] TEST MODE: Setting error for non-empty path")
            return gr.update(elem_classes=["error"])
        else:
            print("[DEBUG] TEST MODE: Clearing classes for empty path")
            return gr.update(elem_classes=[])

        # 本来のロジック（後で復活）
        # is_valid, message = self.cli_validator.validate_dit_file_path(file_path)
        # print(f"[DEBUG] Validation result: valid={is_valid}, message='{message}'")
        # if is_valid:
        #     return gr.update(elem_classes=[])
        # else:
        #     return gr.update(elem_classes=["error"])

    def create_model_section(self) -> List[Any]:
        """モデル設定セクションを静的に作成（現在の見た目を維持）"""
        components: List[Any] = []

        with gr.Accordion("モデル・出力設定", open=True):
            # 基本出力設定
            with gr.Row():
                # 出力ディレクトリ
                output_dir_param = self.parameters.get("output_dir")
                if output_dir_param:
                    od_enabled = gr.Checkbox(
                        label="有効",
                        value=output_dir_param.required,
                        elem_id="param-output_dir-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    od_value = gr.Textbox(
                        label=output_dir_param.display_name,
                        value=output_dir_param.default_value,
                        info=output_dir_param.help_text,
                        elem_id="param-output_dir-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([od_enabled, od_value])
                    self._register_component(
                        "param-output_dir-enabled", od_enabled, "output_dir", "enabled"
                    )
                    self._register_component(
                        "param-output_dir-value", od_value, "output_dir", "value"
                    )

                # 出力名
                output_name_param = self.parameters.get("output_name")
                if output_name_param:
                    on_enabled = gr.Checkbox(
                        label="有効",
                        value=output_name_param.required,
                        elem_id="param-output_name-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    on_value = gr.Textbox(
                        label=output_name_param.display_name,
                        value=output_name_param.default_value,
                        info=output_name_param.help_text,
                        elem_id="param-output_name-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([on_enabled, on_value])
                    self._register_component(
                        "param-output_name-enabled",
                        on_enabled,
                        "output_name",
                        "enabled",
                    )
                    self._register_component(
                        "param-output_name-value", on_value, "output_name", "value"
                    )

            # モデルパス設定
            # DiTパス - 現在の見た目を維持
            with gr.Row():
                dit_param = self.parameters.get("dit")
                if dit_param:
                    dit_enabled = gr.Checkbox(
                        label="有効",
                        value=dit_param.required,
                        elem_id="param-dit-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    dit_value = gr.Textbox(
                        label=dit_param.display_name,  # --dit
                        value=dit_param.default_value,
                        info=dit_param.help_text,  # DiTチェックポイントパス
                        elem_id="param-dit-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([dit_enabled, dit_value])
                    self._register_component(
                        "param-dit-enabled", dit_enabled, "dit", "enabled"
                    )
                    self._register_component(
                        "param-dit-value", dit_value, "dit", "value"
                    )

                    # --ditリアルタイム検証設定
                    dit_value.change(
                        fn=self._validate_dit_realtime,
                        inputs=[dit_value],
                        outputs=[dit_value],
                    )

            # VAEパス - 現在の見た目を維持
            with gr.Row():
                vae_param = self.parameters.get("vae")
                if vae_param:
                    vae_enabled = gr.Checkbox(
                        label="有効",
                        value=vae_param.required,
                        elem_id="param-vae-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    vae_value = gr.Textbox(
                        label=vae_param.display_name,  # --vae
                        value=vae_param.default_value,
                        info=vae_param.help_text,  # VAEチェックポイントパス
                        elem_id="param-vae-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([vae_enabled, vae_value])
                    self._register_component(
                        "param-vae-enabled", vae_enabled, "vae", "enabled"
                    )
                    self._register_component(
                        "param-vae-value", vae_value, "vae", "value"
                    )

                # VAE dtype
                vae_dtype_param = self.parameters.get("vae_dtype")
                if vae_dtype_param:
                    vae_dtype_enabled = gr.Checkbox(
                        label="有効",
                        value=vae_dtype_param.required,
                        elem_id="param-vae_dtype-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    vae_dtype_value = gr.Dropdown(
                        label=vae_dtype_param.display_name,
                        choices=vae_dtype_param.choices,
                        value=vae_dtype_param.default_value,
                        info=vae_dtype_param.help_text,
                        elem_id="param-vae_dtype-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([vae_dtype_enabled, vae_dtype_value])
                    self._register_component(
                        "param-vae_dtype-enabled",
                        vae_dtype_enabled,
                        "vae_dtype",
                        "enabled",
                    )
                    self._register_component(
                        "param-vae_dtype-value", vae_dtype_value, "vae_dtype", "value"
                    )

            # Text Encoder
            with gr.Row():
                te_param = self.parameters.get("text_encoder")
                if te_param:
                    te_enabled = gr.Checkbox(
                        label="有効",
                        value=te_param.required,
                        elem_id="param-text_encoder-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    te_value = gr.Textbox(
                        label=te_param.display_name,
                        value=te_param.default_value,
                        info=te_param.help_text,
                        elem_id="param-text_encoder-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([te_enabled, te_value])
                    self._register_component(
                        "param-text_encoder-enabled",
                        te_enabled,
                        "text_encoder",
                        "enabled",
                    )
                    self._register_component(
                        "param-text_encoder-value", te_value, "text_encoder", "value"
                    )

        return components

    def create_training_section(self) -> List[Any]:
        """学習設定セクションを静的に作成（現在の見た目を維持）"""
        components: List[Any] = []

        with gr.Accordion("基本学習設定", open=True):
            # データセット設定とseed
            with gr.Row():
                dataset_param = self.parameters.get("dataset_config")
                if dataset_param:
                    ds_enabled = gr.Checkbox(
                        label="有効",
                        value=dataset_param.required,
                        elem_id="param-dataset_config-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    ds_value = gr.Textbox(
                        label=dataset_param.display_name,
                        value=dataset_param.default_value,
                        info=dataset_param.help_text,
                        elem_id="param-dataset_config-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([ds_enabled, ds_value])
                    self._register_component(
                        "param-dataset_config-enabled",
                        ds_enabled,
                        "dataset_config",
                        "enabled",
                    )
                    self._register_component(
                        "param-dataset_config-value",
                        ds_value,
                        "dataset_config",
                        "value",
                    )

                seed_param = self.parameters.get("seed")
                if seed_param:
                    seed_enabled = gr.Checkbox(
                        label="有効",
                        value=seed_param.required,
                        elem_id="param-seed-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    seed_value = gr.Number(
                        label=seed_param.display_name,
                        value=seed_param.default_value,
                        info=seed_param.help_text,
                        elem_id="param-seed-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([seed_enabled, seed_value])
                    self._register_component(
                        "param-seed-enabled", seed_enabled, "seed", "enabled"
                    )
                    self._register_component(
                        "param-seed-value", seed_value, "seed", "value"
                    )

            # エポック数とステップ数
            with gr.Row():
                epochs_param = self.parameters.get("max_train_epochs")
                if epochs_param:
                    epochs_enabled = gr.Checkbox(
                        label="有効",
                        value=epochs_param.required,
                        elem_id="param-max_train_epochs-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    epochs_value = gr.Number(
                        label=epochs_param.display_name,
                        value=epochs_param.default_value,
                        info=epochs_param.help_text,
                        elem_id="param-max_train_epochs-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([epochs_enabled, epochs_value])
                    self._register_component(
                        "param-max_train_epochs-enabled",
                        epochs_enabled,
                        "max_train_epochs",
                        "enabled",
                    )
                    self._register_component(
                        "param-max_train_epochs-value",
                        epochs_value,
                        "max_train_epochs",
                        "value",
                    )

                steps_param = self.parameters.get("max_train_steps")
                if steps_param:
                    steps_enabled = gr.Checkbox(
                        label="有効",
                        value=steps_param.required,
                        elem_id="param-max_train_steps-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    steps_value = gr.Number(
                        label=steps_param.display_name,
                        value=steps_param.default_value,
                        info=steps_param.help_text,
                        elem_id="param-max_train_steps-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([steps_enabled, steps_value])
                    self._register_component(
                        "param-max_train_steps-enabled",
                        steps_enabled,
                        "max_train_steps",
                        "enabled",
                    )
                    self._register_component(
                        "param-max_train_steps-value",
                        steps_value,
                        "max_train_steps",
                        "value",
                    )

                # 保存間隔
                save_epochs_param = self.parameters.get("save_every_n_epochs")
                if save_epochs_param:
                    save_epochs_enabled = gr.Checkbox(
                        label="有効",
                        value=save_epochs_param.required,
                        elem_id="param-save_every_n_epochs-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    save_epochs_value = gr.Number(
                        label=save_epochs_param.display_name,
                        value=save_epochs_param.default_value,
                        info=save_epochs_param.help_text,
                        elem_id="param-save_every_n_epochs-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([save_epochs_enabled, save_epochs_value])
                    self._register_component(
                        "param-save_every_n_epochs-enabled",
                        save_epochs_enabled,
                        "save_every_n_epochs",
                        "enabled",
                    )
                    self._register_component(
                        "param-save_every_n_epochs-value",
                        save_epochs_value,
                        "save_every_n_epochs",
                        "value",
                    )

        return components

    def create_network_section(self) -> List[Any]:
        """ネットワーク設定セクションを静的に作成"""
        components: List[Any] = []

        with gr.Accordion("ネットワーク設定", open=True):
            # ネットワークモジュール
            with gr.Row():
                network_module_param = self.parameters.get("network_module")
                if network_module_param:
                    nm_enabled = gr.Checkbox(
                        label="有効",
                        value=network_module_param.required,
                        elem_id="param-network_module-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    nm_value = gr.Textbox(
                        label=network_module_param.display_name,
                        value=network_module_param.default_value,
                        info=network_module_param.help_text,
                        elem_id="param-network_module-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([nm_enabled, nm_value])
                    self._register_component(
                        "param-network_module-enabled",
                        nm_enabled,
                        "network_module",
                        "enabled",
                    )
                    self._register_component(
                        "param-network_module-value",
                        nm_value,
                        "network_module",
                        "value",
                    )

            # Dim と Alpha
            with gr.Row():
                dim_param = self.parameters.get("network_dim")
                if dim_param:
                    dim_enabled = gr.Checkbox(
                        label="有効",
                        value=dim_param.required,
                        elem_id="param-network_dim-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    dim_value = gr.Number(
                        label=dim_param.display_name,
                        value=dim_param.default_value,
                        info=dim_param.help_text,
                        elem_id="param-network_dim-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([dim_enabled, dim_value])
                    self._register_component(
                        "param-network_dim-enabled",
                        dim_enabled,
                        "network_dim",
                        "enabled",
                    )
                    self._register_component(
                        "param-network_dim-value", dim_value, "network_dim", "value"
                    )

                alpha_param = self.parameters.get("network_alpha")
                if alpha_param:
                    alpha_enabled = gr.Checkbox(
                        label="有効",
                        value=alpha_param.required,
                        elem_id="param-network_alpha-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    alpha_value = gr.Number(
                        label=alpha_param.display_name,
                        value=alpha_param.default_value,
                        info=alpha_param.help_text,
                        elem_id="param-network_alpha-value",
                        scale=1,
                        interactive=True,
                    )
                    components.extend([alpha_enabled, alpha_value])
                    self._register_component(
                        "param-network_alpha-enabled",
                        alpha_enabled,
                        "network_alpha",
                        "enabled",
                    )
                    self._register_component(
                        "param-network_alpha-value",
                        alpha_value,
                        "network_alpha",
                        "value",
                    )

        return components

    def create_optimizer_section(self) -> List[Any]:
        """オプティマイザ設定セクションを静的に作成"""
        components: List[Any] = []

        with gr.Accordion("オプティマイザ設定", open=False):
            # オプティマイザタイプ
            with gr.Row():
                optimizer_param = self.parameters.get("optimizer_type")
                if optimizer_param:
                    opt_enabled = gr.Checkbox(
                        label="有効",
                        value=optimizer_param.required,
                        elem_id="param-optimizer_type-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    opt_value = gr.Dropdown(
                        label=optimizer_param.display_name,
                        choices=optimizer_param.choices,
                        value=optimizer_param.default_value,
                        info=optimizer_param.help_text,
                        elem_id="param-optimizer_type-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([opt_enabled, opt_value])
                    self._register_component(
                        "param-optimizer_type-enabled",
                        opt_enabled,
                        "optimizer_type",
                        "enabled",
                    )
                    self._register_component(
                        "param-optimizer_type-value",
                        opt_value,
                        "optimizer_type",
                        "value",
                    )

            # 学習率
            with gr.Row():
                lr_param = self.parameters.get("learning_rate")
                if lr_param:
                    lr_enabled = gr.Checkbox(
                        label="有効",
                        value=lr_param.required,
                        elem_id="param-learning_rate-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    lr_value = gr.Number(
                        label=lr_param.display_name,
                        value=lr_param.default_value,
                        info=lr_param.help_text,
                        elem_id="param-learning_rate-value",
                        scale=1,
                        interactive=True,
                    )
                    components.extend([lr_enabled, lr_value])
                    self._register_component(
                        "param-learning_rate-enabled",
                        lr_enabled,
                        "learning_rate",
                        "enabled",
                    )
                    self._register_component(
                        "param-learning_rate-value", lr_value, "learning_rate", "value"
                    )

                # LRスケジューラ
                lr_scheduler_param = self.parameters.get("lr_scheduler")
                if lr_scheduler_param:
                    lrs_enabled = gr.Checkbox(
                        label="有効",
                        value=lr_scheduler_param.required,
                        elem_id="param-lr_scheduler-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    lrs_value = gr.Dropdown(
                        label=lr_scheduler_param.display_name,
                        choices=lr_scheduler_param.choices,
                        value=lr_scheduler_param.default_value,
                        info=lr_scheduler_param.help_text,
                        elem_id="param-lr_scheduler-value",
                        scale=2,
                        interactive=True,
                    )
                    components.extend([lrs_enabled, lrs_value])
                    self._register_component(
                        "param-lr_scheduler-enabled",
                        lrs_enabled,
                        "lr_scheduler",
                        "enabled",
                    )
                    self._register_component(
                        "param-lr_scheduler-value", lrs_value, "lr_scheduler", "value"
                    )

        return components

    def create_advanced_section(self) -> List[Any]:
        """高度な設定セクションを静的に作成"""
        components: List[Any] = []

        with gr.Accordion("高度な設定", open=False):
            # バッチサイズ
            with gr.Row():
                batch_param = self.parameters.get("train_batch_size")
                if batch_param:
                    batch_enabled = gr.Checkbox(
                        label="有効",
                        value=batch_param.required,
                        elem_id="param-train_batch_size-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    batch_value = gr.Number(
                        label=batch_param.display_name,
                        value=batch_param.default_value,
                        info=batch_param.help_text,
                        elem_id="param-train_batch_size-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([batch_enabled, batch_value])
                    self._register_component(
                        "param-train_batch_size-enabled",
                        batch_enabled,
                        "train_batch_size",
                        "enabled",
                    )
                    self._register_component(
                        "param-train_batch_size-value",
                        batch_value,
                        "train_batch_size",
                        "value",
                    )

                # グラディエントアキュムレーション
                grad_acc_param = self.parameters.get("gradient_accumulation_steps")
                if grad_acc_param:
                    grad_acc_enabled = gr.Checkbox(
                        label="有効",
                        value=grad_acc_param.required,
                        elem_id="param-gradient_accumulation_steps-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    grad_acc_value = gr.Number(
                        label=grad_acc_param.display_name,
                        value=grad_acc_param.default_value,
                        info=grad_acc_param.help_text,
                        elem_id="param-gradient_accumulation_steps-value",
                        precision=0,
                        scale=1,
                        interactive=True,
                    )
                    components.extend([grad_acc_enabled, grad_acc_value])
                    self._register_component(
                        "param-gradient_accumulation_steps-enabled",
                        grad_acc_enabled,
                        "gradient_accumulation_steps",
                        "enabled",
                    )
                    self._register_component(
                        "param-gradient_accumulation_steps-value",
                        grad_acc_value,
                        "gradient_accumulation_steps",
                        "value",
                    )

            # Mixed precision
            with gr.Row():
                mixed_param = self.parameters.get("mixed_precision")
                if mixed_param:
                    mixed_enabled = gr.Checkbox(
                        label="有効",
                        value=mixed_param.required,
                        elem_id="param-mixed_precision-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    mixed_value = gr.Dropdown(
                        label=mixed_param.display_name,
                        choices=mixed_param.choices,
                        value=mixed_param.default_value,
                        info=mixed_param.help_text,
                        elem_id="param-mixed_precision-value",
                        scale=2,
                        interactive=True,
                    )
                    components.extend([mixed_enabled, mixed_value])
                    self._register_component(
                        "param-mixed_precision-enabled",
                        mixed_enabled,
                        "mixed_precision",
                        "enabled",
                    )
                    self._register_component(
                        "param-mixed_precision-value",
                        mixed_value,
                        "mixed_precision",
                        "value",
                    )

                # Gradient checkpointing
                grad_check_param = self.parameters.get("gradient_checkpointing")
                if grad_check_param:
                    grad_check = gr.Checkbox(
                        label=grad_check_param.display_name,
                        value=grad_check_param.default_value,
                        info=grad_check_param.help_text,
                        elem_id="param-gradient_checkpointing",
                        scale=1,
                        interactive=True,
                    )
                    components.append(grad_check)
                    self._register_component(
                        "param-gradient_checkpointing",
                        grad_check,
                        "gradient_checkpointing",
                        "checkbox",
                    )

        return components

    def create_dynamic_optimizer_section(
        self, optimizer_ui, template_manager
    ) -> List[Any]:
        """動的オプティマイザー設定セクション（V4統合対応）"""
        components: List[Any] = []

        with gr.Accordion("オプティマイザー設定（動的）", open=True):
            # テンプレート駆動型オプティマイザー選択
            with gr.Row():
                optimizer_choices = template_manager.get_optimizer_choices()
                if optimizer_choices:
                    opt_enabled = gr.Checkbox(
                        label="有効",
                        value=True,
                        elem_id="param-optimizer_type-enabled",
                        scale=0,
                        min_width=80,
                        interactive=True,
                    )
                    opt_value = gr.Dropdown(
                        label="オプティマイザー選択",
                        choices=optimizer_choices,
                        value=optimizer_choices[0],
                        info="使用するオプティマイザーを選択",
                        elem_id="param-optimizer_type-value",
                        scale=3,
                        interactive=True,
                    )
                    components.extend([opt_enabled, opt_value])
                    self._register_component(
                        "param-optimizer_type-enabled",
                        opt_enabled,
                        "optimizer_type",
                        "enabled",
                    )
                    self._register_component(
                        "param-optimizer_type-value",
                        opt_value,
                        "optimizer_type",
                        "value",
                    )

            # 動的引数コンテナ（optimizer_argsはcreate_arguments_containerで作成）
            # これは動的に更新されるため、ここでは参照のみ

        return components

    def create_enhanced_sections(self) -> Dict[str, List[Any]]:
        """強化版セクション構築（V4統合対応）"""
        sections = {
            "model": self.create_model_section(),
            "training": self.create_training_section(),
            "network": self.create_network_section(),
            "optimizer": self.create_optimizer_section(),
            "advanced": self.create_advanced_section(),
        }
        return sections

    def build_all_sections(self) -> Dict[str, List[Any]]:
        """全セクションを構築"""
        sections = {
            "model": self.create_model_section(),
            "training": self.create_training_section(),
            "network": self.create_network_section(),
            "optimizer": self.create_optimizer_section(),
            "advanced": self.create_advanced_section(),
        }
        return sections

    def get_component_count(self) -> int:
        """登録されたコンポーネント数を取得"""
        return len(self.registry)

    def get_parameter_info(self, param_name: str) -> Dict[str, Any]:
        """パラメータ情報を取得"""
        param_config = self.parameters.get(param_name)
        if param_config:
            return {
                "name": param_config.name,
                "display_name": param_config.display_name,
                "param_type": param_config.param_type,
                "default_value": param_config.default_value,
                "choices": getattr(param_config, "choices", None),
                "required": param_config.required,
                "help_text": param_config.help_text,
            }
        return {}

    def validate_registry(self) -> Dict[str, Any]:
        """レジストリの整合性を検証"""
        validation_result: Dict[str, Any] = {
            "total_components": len(self.registry),
            "enabled_components": 0,
            "value_components": 0,
            "missing_param_configs": [],
            "invalid_elem_ids": [],
        }

        for elem_id, reg_info in self.registry.items():
            role = reg_info.get("role")
            if role == "enabled":
                validation_result["enabled_components"] += 1
            elif role == "value":
                validation_result["value_components"] += 1

            param_config = reg_info.get("param_config")
            if not param_config:
                validation_result["missing_param_configs"].append(elem_id)

            if not elem_id.startswith("param-"):
                validation_result["invalid_elem_ids"].append(elem_id)

        return validation_result
