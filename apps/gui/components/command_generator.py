"""
コマンド生成ユーティリティ
"""

from typing import Dict, Any, List


class CommandGenerator:
    """コマンド生成クラス"""

    def __init__(self):
        self.musubi_tuner_base_path = "src/musubi_tuner/"
        self.script_paths = {
            "precache": "qwen_image_cache_latents.py",
            "text_encoder": "qwen_image_cache_text_encoder_outputs.py",
            "training": "qwen_image_train_network.py",
        }

    def generate_precache_command(
        self, params: Dict[str, Any], use_newlines: bool = True
    ) -> str:
        """潜在変数キャッシュ作成コマンド生成"""
        base_command = (
            f"python {self.musubi_tuner_base_path}{self.script_paths['precache']}"
        )

        # Pre-caching用パラメータのみ
        precache_params = ["dataset_config", "vae"]

        args = []
        for param in precache_params:
            if param in params and params[param] is not None:
                value = params[param]
                if isinstance(value, bool):
                    if value:
                        args.append(f"--{param}")
                else:
                    # チェックが入っていれば空文字でも引数として追加
                    if isinstance(value, str):
                        if value.strip() == "":
                            # 空文字の場合は引数名のみ追加
                            args.append(f"--{param}")
                        elif " " in str(value):
                            args.append(f'--{param} "{value}"')
                        else:
                            args.append(f"--{param} {value}")
                    else:
                        args.append(f"--{param} {value}")

        # 固定引数を末尾に追加
        args.append("--vae_chunk_size 32")
        args.append("--vae_tiling")

        # argsは固定引数が追加されているため常に存在する
        if use_newlines:
            return f"{base_command} \\\n  " + " \\\n  ".join(args)
        else:
            return f"{base_command} " + " ".join(args)

    def generate_text_encoder_command(
        self, params: Dict[str, Any], use_newlines: bool = True
    ) -> str:
        """テキストエンコーダーキャッシュ作成コマンド生成"""
        base_command = (
            f"python {self.musubi_tuner_base_path}{self.script_paths['text_encoder']}"
        )

        # Text Encoder Pre-caching用パラメータのみ
        text_encoder_params = ["dataset_config", "text_encoder"]

        args = []
        for param in text_encoder_params:
            if param in params and params[param] is not None:
                value = params[param]
                if isinstance(value, bool):
                    if value:
                        args.append(f"--{param}")
                else:
                    # チェックが入っていれば空文字でも引数として追加
                    if isinstance(value, str):
                        if value.strip() == "":
                            # 空文字の場合は引数名のみ追加
                            args.append(f"--{param}")
                        elif " " in str(value):
                            args.append(f'--{param} "{value}"')
                        else:
                            args.append(f"--{param} {value}")
                    else:
                        args.append(f"--{param} {value}")

        # 固定引数を末尾に追加
        args.append("--batch_size 16")

        # argsは固定引数が追加されているため常に存在する
        if use_newlines:
            return f"{base_command} \\\n  " + " \\\n  ".join(args)
        else:
            return f"{base_command} " + " ".join(args)

    def generate_training_command(
        self, params: Dict[str, Any], use_newlines: bool = True
    ) -> str:
        """学習コマンド生成（accelerate launch使用）"""

        # accelerate launch プレフィックス処理
        accelerate_args = self._build_accelerate_args(params)
        base_command = f"accelerate launch {accelerate_args} {self.musubi_tuner_base_path}{self.script_paths['training']}"

        args = []

        # 学習用パラメータ（全タブの項目を含む）
        training_params = [
            # 1.1 モデルパス設定
            "dit",
            "vae",
            "vae_dtype",
            "text_encoder",
            # 2.1 基本出力設定
            "output_dir",
            "output_name",
            "resume",
            # 2.2 保存スケジュール設定
            "save_every_n_epochs",
            "save_every_n_steps",
            "save_last_n_epochs",
            "save_last_n_epochs_state",
            "save_last_n_steps",
            "save_last_n_steps_state",
            "save_state",
            "save_state_on_train_end",
            # 2.3 メタデータ設定
            "metadata_title",
            "metadata_author",
            "metadata_description",
            "metadata_license",
            "metadata_tags",
            "no_metadata",
            # 3.1 基本パラメータ（基本学習設定タブ）
            "config_file",
            "dataset_config",
            "seed",
            "max_train_steps",
            "max_train_epochs",
            "training_comment",
            # 3.2 データローダー設定（基本学習設定タブ）
            "max_data_loader_n_workers",
            "persistent_data_loader_workers",
            # 3.3 最適化設定（基本学習設定タブ）
            "gradient_checkpointing",
            "gradient_accumulation_steps",
            "mixed_precision",
            "max_grad_norm",
            # 3.4-3.5 オプティマイザー・学習率設定
            "optimizer_type",
            "learning_rate",
            "lr_scheduler",
            "lr_warmup_steps",
            "lr_decay_steps",
            "lr_scheduler_num_cycles",
            "lr_scheduler_power",
            "lr_scheduler_min_lr_ratio",
            "lr_scheduler_timescale",
            "lr_scheduler_type",
            # 4.1 ネットワーク設定
            "network_module",
            "network_dim",
            "network_alpha",
            "network_weights",  # 追加
            "network_dropout",  # 追加
            "dim_from_weights",  # 追加
            "scale_weight_norms",  # 追加
            "network_args",  # 追加
            "base_weights",  # 追加
            "base_weights_multiplier",  # 追加
            # 4.2 タイムステップ設定
            "timestep_sampling",  # 追加
            "discrete_flow_shift",  # 追加
            "sigmoid_scale",  # 追加
            "weighting_scheme",  # 追加
            "logit_mean",  # 追加
            "logit_std",  # 追加
            "mode_scale",  # 追加
            "min_timestep",  # 追加
            "max_timestep",  # 追加
            "preserve_distribution_shape",  # 追加
            "show_timesteps",  # 追加
            "guidance_scale",  # 追加
            # 5.1 アテンション最適化
            "sdpa",
            "flash_attn",
            "sage_attn",  # 追加
            "xformers",
            "flash3",  # 追加
            "split_attn",  # 追加
            # 5.2 精度・メモリ最適化
            "fp8_base",
            "fp8_scaled",  # 追加
            "fp8_vl",  # 追加
            "blocks_to_swap",
            "img_in_txt_in_offloading",  # 追加
            "cache_latents",
            "vae_chunk_size",
            "vae_tiling",
            # 5.3 コンパイル最適化
            "dynamo_backend",
            "dynamo_mode",
            "dynamo_fullgraph",  # 追加
            "dynamo_dynamic",  # 追加
            # 5.4 分散処理設定
            "ddp_timeout",
            "ddp_gradient_as_bucket_view",  # 追加
            "ddp_static_graph",  # 追加
            "train_batch_size",
            # 6.1 ログ出力設定
            "logging_dir",
            "log_with",
            "log_prefix",  # 追加
            "log_tracker_name",  # 追加
            "wandb_run_name",  # 追加
            "wandb_api_key",  # 追加
            "log_tracker_config",  # 追加
            "log_config",  # 追加
            # 6.2 サンプリング設定
            "sample_every_n_steps",  # 追加
            "sample_at_first",  # 追加
            "sample_every_n_epochs",  # 追加
            "sample_prompts",  # 追加
            # 6.3 外部連携設定（HuggingFace等）
            "huggingface_repo_id",  # 追加
            "huggingface_path_in_repo",  # 追加
            "huggingface_token",  # 追加
            "huggingface_repo_type",  # 追加
            "huggingface_repo_visibility",  # 追加
            "save_state_to_huggingface",  # 追加
            "resume_from_huggingface",  # 追加
            "async_upload",  # 追加
            # その他
            "save_precision",
            "save_model_as",
        ]

        for param in training_params:
            if param == "optimizer_type":
                # optimizer_typeは後で個別処理
                continue

            if param in params and params[param] is not None:
                value = params[param]

                if isinstance(value, bool):
                    if value:
                        args.append(f"--{param}")
                else:
                    # チェックが入っていれば空文字でも引数として追加
                    if isinstance(value, str):
                        if value.strip() == "":
                            # 空文字の場合は引数名のみ追加
                            args.append(f"--{param}")
                        elif " " in str(value):
                            args.append(f'--{param} "{value}"')
                        else:
                            args.append(f"--{param} {value}")
                    else:
                        args.append(f"--{param} {value}")

        # オプティマイザー設定
        optimizer_type = params.get("optimizer_type")
        if optimizer_type:
            args.append(f"--optimizer_type {optimizer_type}")

        # optimizer_argsの個別処理
        optimizer_args_list = self._build_optimizer_args_list(params)
        args.extend(optimizer_args_list)

        # カスタム引数を末尾に追加（引数名なし）
        custom_args = params.get("custom_args")
        if custom_args and custom_args.strip():
            # カスタム引数をそのまま末尾に追加
            args.append(custom_args.strip())

        # コマンド組み立て
        if args:
            if use_newlines:
                command = f"{base_command} \\\n  " + " \\\n  ".join(args)
            else:
                command = f"{base_command} " + " ".join(args)
        else:
            command = base_command

        return command

    def _build_accelerate_args(self, params: Dict[str, Any]) -> str:
        """accelerate launch用引数構築"""
        accelerate_args = []

        # CPUスレッド数（デフォルト: 1）
        accelerate_args.append("--num_cpu_threads_per_process 1")

        # 混合精度（固定値bf16）
        accelerate_args.append("--mixed_precision bf16")

        return " ".join(accelerate_args)

    def _build_optimizer_args_list(self, params: Dict[str, Any]) -> List[str]:
        """optimizer_argsを個別引数のリストとして生成"""
        optimizer_type = params.get("optimizer_type")
        if not optimizer_type or optimizer_type == "Custom...":
            return []

        optimizer_args = params.get("optimizer_args", {})
        if not optimizer_args:
            return []

        args_list = []
        for key, value in optimizer_args.items():
            if value is None or value == "":
                continue

            # タプル形式（betasなど）の処理
            if key in ["betas"] and isinstance(value, str) and "(" in value:
                args_list.append(f"--optimizer_args {key}={value}")
            # 真偽値の処理
            elif value in ["true", "false"]:
                args_list.append(f"--optimizer_args {key}={value}")
            # その他の値
            else:
                args_list.append(f"--optimizer_args {key}={value}")

        return args_list

    def generate_all_commands(
        self, params: Dict[str, Any], use_newlines: bool = True
    ) -> Dict[str, str]:
        """全コマンドを生成"""
        return {
            "precache": self.generate_precache_command(params, use_newlines),
            "text_encoder": self.generate_text_encoder_command(params, use_newlines),
            "training": self.generate_training_command(params, use_newlines),
        }

    def generate_command_as_list(
        self, command_type: str, params: Dict[str, Any]
    ) -> List[str]:
        """コマンドをリスト形式で生成（subprocess用）"""
        import sys

        # コマンドタイプのマッピング
        type_mapping = {
            "latent_cache": "precache",
            "te_cache": "text_encoder",
            "training": "training",
        }

        mapped_type = type_mapping.get(command_type, command_type)

        # スクリプトパスを取得
        script_path = self.musubi_tuner_base_path + self.script_paths.get(
            mapped_type, ""
        )
        if not script_path:
            return []

        # 基本コマンドリスト
        if mapped_type == "training":
            # accelerate launch用
            command_list = [
                "accelerate",
                "launch",
                "--num_cpu_threads_per_process",
                "1",
                "--mixed_precision",
                "bf16",
                script_path,
            ]
        else:
            # Python直接実行
            command_list = [sys.executable, script_path]

        # パラメータを追加
        if mapped_type == "precache":
            # 潜在変数キャッシュ用パラメータ
            for param in ["dataset_config", "vae"]:
                if param in params and params[param] is not None:
                    value = params[param]
                    if isinstance(value, bool):
                        if value:
                            command_list.append(f"--{param}")
                    else:
                        # 文字列の場合の空文字チェック
                        if isinstance(value, str):
                            if value.strip() == "":
                                # 空文字の場合は引数名のみ追加
                                command_list.append(f"--{param}")
                            else:
                                command_list.extend([f"--{param}", str(value)])
                        elif value != "":
                            command_list.extend([f"--{param}", str(value)])
            # 固定引数
            command_list.extend(["--vae_chunk_size", "32", "--vae_tiling"])

        elif mapped_type == "text_encoder":
            # TEキャッシュ用パラメータ
            for param in ["dataset_config", "text_encoder"]:
                if param in params and params[param] is not None:
                    value = params[param]
                    if isinstance(value, bool):
                        if value:
                            command_list.append(f"--{param}")
                    else:
                        # 文字列の場合の空文字チェック
                        if isinstance(value, str):
                            if value.strip() == "":
                                # 空文字の場合は引数名のみ追加
                                command_list.append(f"--{param}")
                            else:
                                command_list.extend([f"--{param}", str(value)])
                        elif value != "":
                            command_list.extend([f"--{param}", str(value)])
            # 固定引数
            command_list.extend(["--batch_size", "16"])

        elif mapped_type == "training":
            # 学習用パラメータ（全タブの項目）
            training_params = [
                "dit",
                "vae",
                "vae_dtype",
                "text_encoder",
                "output_dir",
                "output_name",
                "resume",
                "save_every_n_epochs",
                "save_every_n_steps",
                "save_last_n_epochs",
                "save_last_n_epochs_state",
                "save_last_n_steps",
                "save_last_n_steps_state",
                "save_state",
                "save_state_on_train_end",
                "metadata_title",
                "metadata_author",
                "metadata_description",
                "metadata_license",
                "metadata_tags",
                "no_metadata",
                "config_file",
                "dataset_config",
                "seed",
                "max_train_steps",
                "max_train_epochs",
                "training_comment",
                "max_data_loader_n_workers",
                "persistent_data_loader_workers",
                "gradient_checkpointing",
                "gradient_accumulation_steps",
                "mixed_precision",
                "max_grad_norm",
                "learning_rate",
                "lr_scheduler",
                "lr_warmup_steps",
                "lr_decay_steps",
                "lr_scheduler_num_cycles",
                "lr_scheduler_power",
                "lr_scheduler_min_lr_ratio",
                "lr_scheduler_timescale",
                "lr_scheduler_type",
                "network_module",
                "network_dim",
                "network_alpha",
                "network_weights",
                "network_dropout",
                "dim_from_weights",
                "scale_weight_norms",
                "network_args",
                "base_weights",
                "base_weights_multiplier",
                "timestep_sampling",
                "discrete_flow_shift",
                "sigmoid_scale",
                "weighting_scheme",
                "logit_mean",
                "logit_std",
                "mode_scale",
                "min_timestep",
                "max_timestep",
                "preserve_distribution_shape",
                "show_timesteps",
                "guidance_scale",
                "sdpa",
                "flash_attn",
                "sage_attn",
                "xformers",
                "flash3",
                "split_attn",
                "fp8_base",
                "fp8_scaled",
                "fp8_vl",
                "blocks_to_swap",
                "img_in_txt_in_offloading",
                "cache_latents",
                "vae_chunk_size",
                "vae_tiling",
                "dynamo_backend",
                "dynamo_mode",
                "dynamo_fullgraph",
                "dynamo_dynamic",
                "ddp_timeout",
                "ddp_gradient_as_bucket_view",
                "ddp_static_graph",
                "train_batch_size",
                "logging_dir",
                "log_with",
                "log_prefix",
                "log_tracker_name",
                "wandb_run_name",
                "wandb_api_key",
                "log_tracker_config",
                "log_config",
                "sample_every_n_steps",
                "sample_at_first",
                "sample_every_n_epochs",
                "sample_prompts",
                "huggingface_repo_id",
                "huggingface_path_in_repo",
                "huggingface_token",
                "huggingface_repo_type",
                "huggingface_repo_visibility",
                "save_state_to_huggingface",
                "resume_from_huggingface",
                "async_upload",
                "save_precision",
                "save_model_as",
            ]

            for param in training_params:
                if param in params and params[param] is not None:
                    value = params[param]
                    if isinstance(value, bool):
                        if value:
                            command_list.append(f"--{param}")
                    else:
                        # 文字列の場合の空文字チェック（generate_training_commandと同じロジック）
                        if isinstance(value, str):
                            if value.strip() == "":
                                # 空文字の場合は引数名のみ追加
                                command_list.append(f"--{param}")
                            else:
                                command_list.extend([f"--{param}", str(value)])
                        elif value != "":
                            command_list.extend([f"--{param}", str(value)])

            # optimizer_type
            if "optimizer_type" in params and params["optimizer_type"]:
                command_list.extend(["--optimizer_type", str(params["optimizer_type"])])

            # optimizer_args
            if "optimizer_args" in params and params["optimizer_args"]:
                for key, value in params["optimizer_args"].items():
                    if value is not None and value != "":
                        command_list.extend(["--optimizer_args", f"{key}={value}"])

        return command_list
