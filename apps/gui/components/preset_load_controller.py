"""統合プリセット読み込み制御クラス

既存の分散処理を統合し、一貫したプリセット読み込みを実現
"""

from typing import Any, Dict, List, Optional, Tuple
import gradio as gr
import json
import logging
import os
from datetime import datetime

# 型ヒント用のインポート（実行時にはインポートしない）
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.gui.components.preset_manager_v2 import PresetManagerV2
    from apps.gui.components.parameter_collector_v4 import ParameterCollectorV4


class PresetLoadController:
    """統合プリセット読み込み制御クラス

    既存の分散処理を統合し、一貫したプリセット読み込みを実現
    optimizer_args値セット問題を根本解決
    """

    def __init__(
        self, preset_manager: "PresetManagerV2", collector: "ParameterCollectorV4"
    ):
        """初期化

        Args:
            preset_manager: プリセット管理器（V2）
            collector: パラメータ収集器（V3）
        """
        self.preset_manager = preset_manager
        self.collector = collector
        self.logger = logging.getLogger(__name__)
        self.last_optimizer_type = None  # 最後に設定したoptimizer_type値を記録
        self.delayed_args_data: Optional[Dict[str, Any]] = (
            None  # 遅延実行用のoptimizer_argsデータ
        )

    def load_preset_phase1_unified(
        self,
        selected_filename: str,
        optimizer_type_component: Any,
        all_components: List[Any],
        optimizer_args_components: List[Any],
    ) -> tuple:
        """Phase 1統合: optimizer_type変更検出と適切な処理を実行"""
        try:
            self.logger.debug(f"Phase 1 unified start: {selected_filename}")

            # プリセット読み込み
            success, preset_params, load_message = self._load_preset_file(
                selected_filename
            )
            if not success:
                error_count = len(all_components) + len(optimizer_args_components)
                return (
                    "❌ プリセットファイルの読み込みに失敗しました",
                    gr.update(),
                ) + tuple(gr.update() for _ in range(error_count))

            # optimizer_typeの確認と更新
            current_optimizer_type = getattr(optimizer_type_component, "value", "")
            preset_optimizer_type_data = preset_params.get("optimizer_type", "")

            if isinstance(preset_optimizer_type_data, dict):
                preset_optimizer_type = preset_optimizer_type_data.get("value", "")
            else:
                preset_optimizer_type = preset_optimizer_type_data

            # 型比較（ログは開発時のみ必要）
            self.logger.debug(
                f"Current: '{current_optimizer_type}', Preset: '{preset_optimizer_type}'"
            )

            # 正規化した比較
            current_normalized = (
                str(current_optimizer_type).strip() if current_optimizer_type else ""
            )
            preset_normalized = (
                str(preset_optimizer_type).strip() if preset_optimizer_type else ""
            )
            type_changed = current_normalized != preset_normalized

            self.logger.debug(f"Optimizer type changed: {type_changed}")

            # 必ず統合処理で全更新を実行
            return self.load_preset_unified(
                selected_filename,
                optimizer_type_component,
                all_components,
                optimizer_args_components,
            )

        except Exception as e:
            self.logger.error(f"Phase 1 unified error: {e}")
            error_count = len(all_components) + len(optimizer_args_components)
            return (f"❌ エラー: {str(e)}", gr.update()) + tuple(
                gr.update() for _ in range(error_count)
            )

    def load_preset_phase1(
        self, selected_filename: str, optimizer_type_component: Any
    ) -> tuple:
        """Phase 1: optimizer_typeのみ更新してUI再生成をトリガー"""
        try:
            self.logger.debug(f"Phase 1 start: {selected_filename}")

            # プリセット読み込み（既存メソッドを使用）
            success, preset_params, load_message = self._load_preset_file(
                selected_filename
            )
            if not success:
                return ("❌ プリセットファイルの読み込みに失敗しました", gr.update())

            # optimizer_typeの確認と更新（強化版）
            current_optimizer_type = getattr(optimizer_type_component, "value", "")
            preset_optimizer_type_data = preset_params.get("optimizer_type", "")

            # optimizer_typeが辞書形式の場合、valueを取得
            if isinstance(preset_optimizer_type_data, dict):
                preset_optimizer_type = preset_optimizer_type_data.get("value", "")
            else:
                preset_optimizer_type = preset_optimizer_type_data

            self.logger.debug(
                f"Current: {current_optimizer_type}, Preset: {preset_optimizer_type}"
            )

            # 空文字列やNoneの処理を含めた強化版比較
            current_normalized = (
                str(current_optimizer_type).strip() if current_optimizer_type else ""
            )
            preset_normalized = (
                str(preset_optimizer_type).strip() if preset_optimizer_type else ""
            )

            type_changed = current_normalized != preset_normalized
            self.logger.debug(f"Type change detected: {type_changed}")

            if type_changed:
                self.logger.info("Optimizer type change detected - Phase 2 required")
                return (
                    f"📋 プリセット '{selected_filename}' 読み込み中... (Phase 1/2)",
                    gr.update(value=preset_optimizer_type),
                )
            else:
                self.logger.debug(
                    "Same optimizer type - proceeding to unified processing"
                )
                # optimizer_type同一時は統合処理を直接実行して全更新を返却
                return self.load_preset_unified(
                    selected_filename, optimizer_type_component, [], []
                )

        except Exception as e:
            self.logger.error(f"Phase 1 error: {e}")
            return (f"❌ エラー: {str(e)}", gr.update())

    def load_preset_phase2_with_updated_type(
        self,
        selected_filename: str,
        preset_dropdown_value: str,
        optimizer_type_component: Any,
        all_components: List[Any],
        optimizer_args_components: List[Any],
    ):
        """Phase 2: optimizer_args含む全体更新（簡素化版）"""
        try:
            self.logger.debug(f"Phase 2 start: {selected_filename}")

            # 既存の統合処理を流用し、強制的にoptimizer_type変更として処理
            self.logger.debug("Phase 2: Executing unified processing")
            result = self.load_preset_unified(
                selected_filename,
                optimizer_type_component,
                all_components,
                optimizer_args_components,
            )
            self.logger.debug(f"Phase 2 result length: {len(result)}")
            return result

        except Exception as e:
            self.logger.error(f"Phase 2 error: {e}")
            error_count = len(all_components) + len(optimizer_args_components)
            return (f"❌ エラー: {str(e)}",) + tuple(
                gr.update() for _ in range(error_count)
            )

    def load_preset_phase2_with_type(
        self,
        selected_filename: str,
        optimizer_type_value: str,
        all_components: List[Any],
        optimizer_args_components: List[Any],
    ):
        """Phase 2: optimizer_args含む全体更新（更新されたoptimizer_type値を使用）"""
        try:
            self.logger.debug(f"Phase 2 start: {selected_filename}")
            self.logger.debug(
                f"Phase 2 received optimizer_type_value: '{optimizer_type_value}' (type: {type(optimizer_type_value)})"
            )

            # プリセット読み込み
            success, preset_params, load_message = self._load_preset_file(
                selected_filename
            )
            if not success:
                return ("❌ プリセットファイルの読み込みに失敗しました",) + tuple(
                    gr.update()
                    for _ in range(len(all_components) + len(optimizer_args_components))
                )

            # Phase 2ではPhase 1で更新されたoptimizer_typeを使用
            current_optimizer_type = optimizer_type_value  # Phase 1からの値

            # プリセットのoptimizer_typeを取得
            preset_optimizer_data = preset_params.get("optimizer_type", {})
            if (
                isinstance(preset_optimizer_data, dict)
                and "value" in preset_optimizer_data
            ):
                preset_optimizer_type = preset_optimizer_data["value"]
            else:
                preset_optimizer_type = (
                    str(preset_optimizer_data) if preset_optimizer_data else ""
                )

            self.logger.debug(
                f"Phase 2 current_optimizer_type: {current_optimizer_type}"
            )
            self.logger.debug(f"Phase 2 preset_optimizer_type: {preset_optimizer_type}")

            # Phase 2では必ずプリセットの値を使用（Phase 1で既に更新済み）
            final_optimizer_type = preset_optimizer_type

            # optimizer_args処理
            optimizer_args_data = preset_params.get("optimizer_args", {})
            if optimizer_args_data and final_optimizer_type:
                self.logger.debug(
                    f"Phase 2 optimizer_args processing: {final_optimizer_type}"
                )

                # UI更新データ作成
                ui_updates = self.collector.optimizer_ui.update_optimizer_ui(
                    final_optimizer_type, preset_values=optimizer_args_data
                )

                if ui_updates and len(ui_updates) > 1:
                    # 通常コンポーネントの更新データ作成（簡素化）
                    all_components_updates = []
                    for comp in all_components:
                        if hasattr(comp, "elem_id") and comp.elem_id:
                            param_name = (
                                comp.elem_id.replace("param-", "")
                                .replace("-enabled", "")
                                .replace("-value", "")
                            )
                            param_data = preset_params.get(param_name, {})
                            if isinstance(param_data, dict):
                                if "enabled" in comp.elem_id:
                                    all_components_updates.append(
                                        gr.update(
                                            value=param_data.get("enabled", False)
                                        )
                                    )
                                elif "value" in comp.elem_id:
                                    all_components_updates.append(
                                        gr.update(value=param_data.get("value", None))
                                    )
                                else:
                                    all_components_updates.append(gr.update())
                            else:
                                all_components_updates.append(gr.update())
                        else:
                            all_components_updates.append(gr.update())

                    optimizer_args_updates = ui_updates[
                        1:
                    ]  # 最初はoptimizer_type、以後がargs

                    success_message = (
                        f"✅ プリセット '{selected_filename}' を正常に読み込みました"
                    )
                    return (
                        (success_message,)
                        + tuple(all_components_updates)
                        + tuple(optimizer_args_updates)
                    )

            # フォールバック
            error_count = len(all_components) + len(optimizer_args_components)
            return ("⚠️ optimizer_argsの処理に失敗しました",) + tuple(
                gr.update() for _ in range(error_count)
            )

        except Exception as e:
            self.logger.error(f"Phase 2 error: {e}")
            error_count = len(all_components) + len(optimizer_args_components)
            return (f"❌ エラー: {str(e)}",) + tuple(
                gr.update() for _ in range(error_count)
            )

    def load_preset_phase2(
        self,
        selected_filename: str,
        optimizer_type_component: Any,
        all_components: List[Any],
        optimizer_args_components: List[Any],
    ):
        """Phase 2: optimizer_args含む全体更新（旧版）"""
        try:
            self.logger.debug(f"Phase 2 start: {selected_filename}")
            self.logger.debug(
                f"Phase 2 optimizer_type_component: {type(optimizer_type_component)}"
            )
            self.logger.debug(
                f"Phase 2 optimizer_type_component.value: {getattr(optimizer_type_component, 'value', 'NO_VALUE')}"
            )

            # 既存の統合プリセット処理を流用
            result = self.load_preset_unified(
                selected_filename,
                optimizer_type_component,
                all_components,
                optimizer_args_components,
            )
            self.logger.debug(f"Phase 2 result length: {len(result)}")
            return result

        except Exception as e:
            self.logger.error(f"Phase 2 error: {e}")
            error_count = len(all_components) + len(optimizer_args_components)
            return (f"❌ エラー: {str(e)}",) + tuple(
                gr.update() for _ in range(error_count)
            )

    def load_preset_unified(
        self,
        selected_filename: str,
        optimizer_type_component: Any,
        all_components: List[Any],
        optimizer_args_components: List[Any],
    ):
        """統合プリセット読み込み処理

        Args:
            selected_filename: プリセットファイル名
            optimizer_type_component: オプティマイザー選択コンポーネント
            all_components: 全通常コンポーネント
            optimizer_args_components: optimizer_argsコンポーネント

        Returns:
            (ステータスメッセージ, *全コンポーネント更新値)
        """
        try:
            # 統合プリセット読み込み処理開始
            self.logger.debug(f"Unified preset loading: {selected_filename}")
            self.logger.debug(
                f"Component counts - all: {len(all_components)}, optimizer_args: {len(optimizer_args_components)}"
            )
            self.logger.info(f"統合プリセット読み込み開始: {selected_filename}")

            # Step 1: プリセットファイル読み込み
            success, preset_params, load_message = self._load_preset_file(
                selected_filename
            )
            if not success:
                return self._create_error_response(
                    len(all_components + optimizer_args_components),
                    f"[NG] {load_message}",
                )

            # Step 2: 現在のUI状態取得（ハイブリッド方式）
            ui_component_value = getattr(optimizer_type_component, "value", "")
            self.logger.debug(f"UI component value: {ui_component_value}")
            self.logger.debug(f"Last recorded value: {self.last_optimizer_type}")

            # プリセットからoptimizer_typeを取得
            preset_optimizer_data = preset_params.get("optimizer_type", {})
            if (
                isinstance(preset_optimizer_data, dict)
                and "value" in preset_optimizer_data
            ):
                preset_optimizer_type = preset_optimizer_data["value"]
            else:
                preset_optimizer_type = (
                    str(preset_optimizer_data) if preset_optimizer_data else ""
                )

            self.logger.debug(f"Preset optimizer_type: {preset_optimizer_type}")

            # 重要: 比較を先に実行してからlast_optimizer_typeを更新
            current_optimizer_type = (
                self.last_optimizer_type
                if self.last_optimizer_type
                else ui_component_value
            )
            optimizer_type_changed = current_optimizer_type != preset_optimizer_type
            self.logger.debug(
                f"Comparison: {current_optimizer_type} vs {preset_optimizer_type} = {optimizer_type_changed}"
            )

            # 比較後にlast_optimizer_typeを更新（次回のため）
            if preset_optimizer_type:
                self.logger.debug(
                    f"Updating last_optimizer_type: {self.last_optimizer_type} → {preset_optimizer_type}"
                )
                self.last_optimizer_type = preset_optimizer_type

            # processed_paramsを作成（既存ロジックを流用）
            current_state = {"current_optimizer_type": current_optimizer_type}
            _, processed_params, change_message = self._process_optimizer_type_change(
                preset_params, current_state
            )

            self.logger.debug(f"Final optimizer_type_changed: {optimizer_type_changed}")
            self.logger.debug(f"Change message: {change_message}")

            # Step 4: プリセット名を取得
            preset_name_value = processed_params.get("_preset_name", "")
            
            # Step 5: 統合UI更新データ作成
            updates, status_message = self._create_unified_update_data(
                processed_params,
                optimizer_type_changed,
                all_components,
                optimizer_args_components,
                selected_filename,
            )

            # Step 6: 成功メッセージ統合
            final_message = f"[OK] {load_message}"
            if change_message:
                final_message += f"\n{change_message}"

            # 最終確認ログは debug レベルに変更
            self.logger.debug(f"Returning {len(updates)} update data items")

            self.logger.info(f"統合プリセット読み込み完了: {selected_filename}")

            return (final_message, preset_name_value, *updates)

        except Exception as e:
            return self._handle_main_exception(
                e, all_components, optimizer_args_components
            )

    def apply_delayed_args(self, optimizer_args_components: List[Any]):
        """遅延実行: optimizer_type変更後のoptimizer_args値設定"""
        try:
            if not self.delayed_args_data:
                self.logger.debug("遅延データなし、スキップ")
                return tuple(gr.update() for _ in optimizer_args_components)

            self.logger.debug(
                f"Delayed execution start: {self.delayed_args_data['filename']}"
            )

            optimizer_type = self.delayed_args_data["optimizer_type"]
            args_data = self.delayed_args_data["args_data"]

            # UI更新を再実行
            ui_updates = self.collector.optimizer_ui.update_optimizer_ui(
                optimizer_type, preset_values=args_data
            )

            if ui_updates and len(ui_updates) > 1:
                args_updates = ui_updates[1:]
                self.logger.info(f"遅延実行成功: {len(args_updates)}個の更新")

                # 遅延データをクリア
                self.delayed_args_data = None

                # 不足分を空更新で補充
                while len(args_updates) < len(optimizer_args_components):
                    args_updates.append(gr.update())

                return tuple(args_updates[: len(optimizer_args_components)])
            else:
                self.logger.error("Delayed execution failed")
                return tuple(gr.update() for _ in optimizer_args_components)

        except Exception as e:
            self.logger.error(f"Delayed execution error: {e}")
            return tuple(gr.update() for _ in optimizer_args_components)

    def apply_delayed_args_with_wait(self, optimizer_args_components: List[Any]):
        """待機付き遅延実行: UI更新完了後のoptimizer_args値設定"""
        try:
            if not self.delayed_args_data:
                self.logger.debug("遅延データなし、スキップ")
                return tuple(gr.update() for _ in optimizer_args_components)

            # UI更新完了を待つ（成功していた0.2秒待機を復元）
            import time

            time.sleep(0.2)
            self.logger.info(
                f"待機付き遅延実行開始: {self.delayed_args_data['filename']}"
            )

            # 通常の遅延実行を呼び出し
            return self.apply_delayed_args(optimizer_args_components)

        except Exception as e:
            self.logger.error(f"Delayed execution with wait error: {e}")
            return tuple(gr.update() for _ in optimizer_args_components)

    def _handle_main_exception(self, e, all_components, optimizer_args_components):
        """load_preset_unifiedの例外ハンドル"""
        self.logger.error(f"統合プリセット処理エラー: {e}", exc_info=True)
        return self._create_error_response(
            len(all_components + optimizer_args_components),
            f"[NG] 統合プリセット処理でエラー: {str(e)}",
        )

    def _load_preset_file(self, filename: str) -> Tuple[bool, Dict[str, Any], str]:
        """プリセットファイルを読み込み、基本的な検証を実行

        Args:
            filename: プリセットファイル名

        Returns:
            (成功フラグ, パラメータ辞書, メッセージ)
        """
        if not filename:
            return False, {}, "プリセットを選択してください"

        try:
            preset_path = os.path.join(self.preset_manager.preset_dir, filename)
            with open(preset_path, "r", encoding="utf-8") as f:
                preset_data = json.load(f)

            if "parameters" not in preset_data:
                return False, {}, "不正なプリセット形式"

            self.logger.info(f"プリセットファイル読み込み成功: {filename}")
            
            # プリセット名を取得（metadata.nameから、なければファイル名から）
            preset_name = ""
            if "metadata" in preset_data and "name" in preset_data["metadata"]:
                preset_name = preset_data["metadata"]["name"]
            else:
                # ファイル名から拡張子を除去してプリセット名とする
                preset_name = os.path.splitext(filename)[0]
            
            # プリセットデータにpreset_nameを追加
            result_data = preset_data["parameters"].copy()
            result_data["_preset_name"] = preset_name
            
            return (
                True,
                result_data,
                f"プリセット '{filename}' を読み込みました",
            )

        except FileNotFoundError:
            return False, {}, f"プリセットファイルが見つかりません: {filename}"
        except json.JSONDecodeError as e:
            return False, {}, f"プリセットファイル形式エラー: {str(e)}"
        except Exception as e:
            return False, {}, f"ファイル読み込みエラー: {str(e)}"

    def _get_current_ui_state(self, optimizer_type_component: Any) -> Dict[str, Any]:
        """現在のUI状態を取得

        Args:
            optimizer_type_component: オプティマイザー選択コンポーネント

        Returns:
            現在のUI状態情報
        """
        return {
            "current_optimizer_type": optimizer_type_component.value
            if optimizer_type_component
            else None,
            "timestamp": datetime.now().isoformat(),
        }

    def _process_optimizer_type_change(
        self, preset_params: Dict[str, Any], current_state: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], str]:
        """optimizer_type変更を検出し、必要に応じてoptimizer_argsを変換

        Args:
            preset_params: プリセットパラメータ
            current_state: 現在のUI状態

        Returns:
            (変更フラグ, 処理済みパラメータ, メッセージ)
        """
        # プリセットのoptimizer_typeを取得
        preset_optimizer_type = None
        if "optimizer_type" in preset_params:
            optimizer_data = preset_params["optimizer_type"]
            if isinstance(optimizer_data, dict) and "value" in optimizer_data:
                preset_optimizer_type = optimizer_data["value"]

        current_optimizer_type = current_state.get("current_optimizer_type")

        # 変更検出
        optimizer_type_changed = (
            preset_optimizer_type and preset_optimizer_type != current_optimizer_type
        )

        if not optimizer_type_changed:
            return False, preset_params, ""

        # 変更がある場合の処理
        message = f"optimizer_type: {current_optimizer_type} → {preset_optimizer_type}"

        # PresetManagerV2の変換ロジックを直接実行
        try:
            processed_params = preset_params.copy()
            conv_message = ""

            # optimizer_argsの変換処理（プリセットのoptimizer_typeを使用）
            preset_optimizer_type = processed_params.get("optimizer_type", {}).get(
                "value", ""
            )
            self.logger.debug("optimizer_args processing start")
            self.logger.debug(
                f"optimizer_args_manager available: {self.preset_manager.optimizer_args_manager is not None}"
            )
            self.logger.debug(f"Using optimizer_type: {preset_optimizer_type}")
            self.logger.debug(
                f"'optimizer_args' in processed_params: {'optimizer_args' in processed_params}"
            )

            if (
                self.preset_manager.optimizer_args_manager
                and preset_optimizer_type
                and "optimizer_args" in processed_params
            ):
                optimizer_args_data = processed_params["optimizer_args"]
                self.logger.debug(f"optimizer_args_data: {optimizer_args_data}")

                # 異なるオプティマイザー間での変換（プリセットのタイプを使用）
                conv_message = f"注意: オプティマイザータイプが {current_optimizer_type} から {preset_optimizer_type} に変更されます"

                # プリセットのオプティマイザーのデフォルト値を取得
                default_args = (
                    self.preset_manager.optimizer_args_manager.get_default_args(
                        preset_optimizer_type
                    )
                )
                self.logger.debug(f"default_args: {default_args}")

                # プリセットの値で上書き（互換性のある引数のみ）
                if isinstance(optimizer_args_data, dict):
                    old_args = optimizer_args_data
                    new_args = {}

                    # プリセットのオプティマイザーのテンプレートの引数名を取得
                    template = self.preset_manager.optimizer_args_manager.get_template_for_optimizer(
                        preset_optimizer_type
                    )
                    if template:
                        valid_arg_names = {arg.name for arg in template}

                        # 互換性のある引数をコピー
                        for arg_name, arg_value in old_args.items():
                            if arg_name in valid_arg_names:
                                new_args[arg_name] = arg_value

                        # デフォルト値で補完
                        for arg_name, default_value in default_args.items():
                            if arg_name not in new_args:
                                new_args[arg_name] = {
                                    "enabled": False,
                                    "value": default_value,
                                }

                        # 更新
                        processed_params["optimizer_args"] = new_args
                        self.logger.info(
                            f"optimizer_args変換完了: {len(new_args)}個の引数"
                        )

                # レジストリの同期
                self.preset_manager.optimizer_args_manager.sync_registry_with_template(
                    preset_optimizer_type
                )

            return (
                True,
                processed_params,
                f"{message}\n{conv_message}" if conv_message else message,
            )

        except Exception as e:
            self.logger.warning(f"optimizer_args変換処理でエラー: {e}")
            # エラー時は元のパラメータを返す
            return (
                True,
                preset_params,
                f"{message}\n警告: optimizer_args変換処理でエラーが発生しました",
            )

    def _create_unified_update_data(
        self,
        processed_params: Dict[str, Any],
        optimizer_type_changed: bool,
        all_components: List[Any],
        optimizer_args_components: List[Any],
        selected_filename: str,
    ) -> Tuple[List[Any], str]:
        """統合されたUI更新データを作成

        Args:
            processed_params: 処理済みパラメータ
            optimizer_type_changed: optimizer_type変更フラグ
            all_components: 全通常コンポーネント
            optimizer_args_components: optimizer_argsコンポーネント

        Returns:
            (更新データリスト, ステータスメッセージ)
        """
        updates = []

        # elem_id変換（optimizer_args含む統合処理）
        elem_id_updates = self._convert_params_to_elem_ids(processed_params)

        # optimizer_argsの処理（型変更時と同一時両方に対応）
        args_updates = []
        optimizer_type_value = None
        if "optimizer_type" in processed_params:
            optimizer_type_value = processed_params["optimizer_type"]["value"]
        preset_optimizer_args = processed_params.get("optimizer_args", {})

        if optimizer_type_value:
            # optimizer_type変更時のGradio制限を考慮した処理
            if optimizer_type_changed:
                self.logger.debug(
                    "optimizer_type changed: UI reconstruction required, optimizer_args deferred"
                )
                self.logger.info("optimizer_type変更検出: レジストリ更新実行")
                optimizer_config = self.collector.template_manager.get_optimizer(
                    optimizer_type_value
                )
                if optimizer_config:
                    # レジストリ更新を確実に実行
                    self.collector.optimizer_ui.args_registry.register_args(
                        optimizer_type_value, optimizer_config.arguments
                    )
                    # 現在のoptimizer設定を更新
                    self.collector.optimizer_ui.current_optimizer = optimizer_type_value
                    self.logger.info(f"レジストリ更新完了: {optimizer_type_value}")

                # optimizer_type変更時は、optimizer_argsのUI表示のみ更新（値は設定しない）
                # optimizer_type変更時はUI構造のみ更新（値は設定しない）
                ui_updates = self.collector.optimizer_ui.update_optimizer_ui(
                    optimizer_type_value
                )
                if ui_updates and len(ui_updates) > 1:
                    # 値をすべて空の更新に変換（UI構造のみ）
                    args_updates = [gr.update() for _ in range(len(ui_updates) - 1)]
                    self.logger.debug(
                        f"optimizer_type changed: empty updates only ({len(args_updates)} items)"
                    )

                # 遅延実行用のoptimizer_argsデータを保存
                delayed_optimizer_args = (
                    preset_optimizer_args if preset_optimizer_args else {}
                )
                self.logger.debug(
                    f"Debug: preset_optimizer_args={bool(preset_optimizer_args)}"
                )
                self.logger.debug(
                    f"Debug: delayed_optimizer_args={bool(delayed_optimizer_args)}, keys={list(delayed_optimizer_args.keys()) if delayed_optimizer_args else []}"
                )

                if delayed_optimizer_args:
                    self.delayed_args_data = {
                        "optimizer_type": optimizer_type_value,
                        "args_data": delayed_optimizer_args,
                        "filename": selected_filename,
                    }
                    self.logger.debug(
                        f"遅延実行用データを保存: {len(delayed_optimizer_args)}個の引数"
                    )
                else:
                    self.logger.debug("Delayed data save skipped: data is empty")
            else:
                # optimizer_type同一時のみ値を設定
                self.logger.debug("Same optimizer type: setting values")
                self.logger.debug(
                    f"Preset optimizer_args available: {bool(preset_optimizer_args)}"
                )
                if preset_optimizer_args:
                    enabled_preset_args = {
                        k: v
                        for k, v in preset_optimizer_args.items()
                        if isinstance(v, dict) and v.get("enabled")
                    }
                    self.logger.debug(
                        f"Enabled preset args count: {len(enabled_preset_args)}"
                    )

            if preset_optimizer_args:  # 常に値設定を実行
                self.logger.info(
                    f"optimizer_args UI更新開始: {list(preset_optimizer_args.keys())}"
                )

                # Gradio内部処理完了を待つ（タイミング問題回避）
                import time

                time.sleep(0.05)  # 50ms待機

                # リトライ機能付きUI更新（修正案から採用）
                max_retries = 3
                ui_updates = None

                for attempt in range(max_retries):
                    try:
                        # 待機時間を段階的に増加
                        if attempt > 0:
                            time.sleep(0.1 * attempt)
                            self.logger.info(
                                f"UI更新リトライ {attempt + 1}/{max_retries}"
                            )

                        ui_updates = self.collector.optimizer_ui.update_optimizer_ui(
                            optimizer_type_value, preset_values=preset_optimizer_args
                        )

                        if ui_updates and len(ui_updates) > 1:
                            args_updates = ui_updates[1:]

                            # 値設定確認
                            enabled_count = sum(
                                1
                                for i in range(0, len(args_updates), 7)
                                if i < len(args_updates)
                                and isinstance(args_updates[i], dict)
                                and args_updates[i].get("value") is True
                            )

                            self.logger.debug(
                                f"UI update success (attempt {attempt + 1}): {len(ui_updates)} total, {enabled_count} enabled"
                            )

                            # 詳細デバッグ: 実際の更新内容を確認
                            if optimizer_type_changed and enabled_count == 0:
                                self.logger.debug(
                                    "【警告】optimizer_type変更時に有効引数が0個です（プリセット項目が無効化されている可能性）"
                                )
                                self.logger.debug(
                                    f"optimizer_type_value: {optimizer_type_value}"
                                )
                                self.logger.debug(
                                    f"preset_optimizer_args keys: {list(preset_optimizer_args.keys())}"
                                )

                                # 最初の5個の更新データを詳細確認
                                for i in range(min(5, len(args_updates))):
                                    update_data = args_updates[i]
                                    self.logger.debug(
                                        f"args_updates[{i}]: {update_data}"
                                    )

                                # OptimizerUI内部状態確認
                                self.logger.debug(
                                    f"OptimizerUI.current_optimizer: {self.collector.optimizer_ui.current_optimizer}"
                                )

                                # テンプレート確認
                                template = (
                                    self.collector.template_manager.get_optimizer(
                                        optimizer_type_value
                                    )
                                )
                                if template:
                                    self.logger.debug(
                                        f"テンプレート引数: {[arg.name for arg in template.arguments]}"
                                    )
                                else:
                                    self.logger.debug("テンプレートが見つかりません")

                            # 成功したらループを抜ける
                            if enabled_count > 0 or not optimizer_type_changed:
                                break

                            # 【最終手段】有効引数が0の場合、強制的に値を設定
                            if (
                                enabled_count == 0
                                and optimizer_type_changed
                                and attempt == max_retries - 1
                            ):
                                self.logger.debug("【最終手段】強制的な値設定を試行")
                                args_updates = self._create_forced_args_updates(
                                    optimizer_type_value, preset_optimizer_args
                                )

                    except Exception as e:
                        self.logger.warning(f"UI更新試行{attempt + 1}失敗: {e}")
                        if attempt == max_retries - 1:
                            # 最終試行も失敗した場合
                            args_updates = []
                            break

        # 全コンポーネントの更新データ作成
        for i, component in enumerate(all_components + optimizer_args_components):
            if hasattr(component, "elem_id") and component.elem_id:
                if component.elem_id.startswith("opt-arg-") and args_updates:
                    # optimizer_args特別処理（変更時・同一時共通）
                    component_idx = i - len(all_components)
                    if component_idx >= 0 and component_idx < len(args_updates):
                        # Gradio UI環境での確実な更新のため、elem_idを明示的に設定
                        update_data = (
                            args_updates[component_idx].copy()
                            if isinstance(args_updates[component_idx], dict)
                            else {}
                        )
                        update_data["elem_id"] = component.elem_id
                        updates.append(update_data)
                        self.logger.debug(
                            f"optimizer_args更新適用: component_idx={component_idx}, elem_id={component.elem_id}"
                        )
                    else:
                        updates.append(gr.update())
                        self.logger.debug(
                            f"optimizer_args範囲外: component_idx={component_idx}, elem_id={component.elem_id}"
                        )
                elif component.elem_id in elem_id_updates:
                    # 通常のコンポーネント更新
                    value = elem_id_updates[component.elem_id]
                    updates.append(self._create_component_update(component, value))
                else:
                    updates.append(gr.update())
            else:
                updates.append(gr.update())

        return updates, "統合プリセット読み込み完了"

    def _create_forced_args_updates(
        self, optimizer_type: str, preset_args: Dict[str, Any]
    ) -> List[Any]:
        """OptimizerUIが失敗した場合の強制的なoptimizer_args更新作成

        Gradioのコンポーネント参照問題を回避するため、
        直接的にgr.update()を構築する
        """
        try:
            self.logger.info(f"強制的args更新作成開始: {optimizer_type}")

            # テンプレート取得
            template = self.collector.template_manager.get_optimizer(optimizer_type)
            if not template:
                self.logger.error("テンプレート取得失敗")
                return []

            # 140個のコンポーネント用更新データを作成
            forced_updates = []
            max_args = 20
            components_per_arg = 7

            for arg_idx in range(max_args):
                if arg_idx < len(template.arguments):
                    arg = template.arguments[arg_idx]

                    # プリセット値があるか確認
                    preset_value = preset_args.get(arg.name)
                    if preset_value and isinstance(preset_value, dict):
                        enabled = preset_value.get("enabled", False)
                        value = preset_value.get("value")

                        self.logger.info(
                            f"強制設定: {arg.name} enabled={enabled} value={value}"
                        )

                        # enabled コンポーネント
                        forced_updates.append(
                            gr.update(
                                visible=True,
                                value=enabled,
                                elem_id=f"opt-arg-{arg_idx}-enabled",
                            )
                        )

                        # UI type判定
                        ui_type = arg.get_ui_component_type()

                        # number コンポーネント
                        if hasattr(ui_type, "name") and "NUMBER" in ui_type.name:
                            forced_updates.append(
                                gr.update(
                                    visible=True,
                                    value=value if enabled else 0,
                                    label=f"--{arg.name}",
                                    elem_id=f"opt-arg-{arg_idx}-number",
                                )
                            )
                        else:
                            forced_updates.append(gr.update(visible=False))

                        # text コンポーネント
                        forced_updates.append(gr.update(visible=False))

                        # checkbox コンポーネント
                        forced_updates.append(gr.update(visible=False))

                        # dropdown コンポーネント
                        if hasattr(ui_type, "name") and "DROPDOWN" in ui_type.name:
                            forced_updates.append(
                                gr.update(
                                    visible=True,
                                    value=str(value) if enabled else None,
                                    label=f"--{arg.name}",
                                    elem_id=f"opt-arg-{arg_idx}-dropdown",
                                )
                            )
                        else:
                            forced_updates.append(gr.update(visible=False))

                        # tuple コンポーネント
                        forced_updates.extend(
                            [
                                gr.update(visible=False),  # tuple-1
                                gr.update(visible=False),  # tuple-2
                            ]
                        )
                    else:
                        # 値なしの場合は非表示
                        forced_updates.extend(
                            [gr.update(visible=False)] * components_per_arg
                        )
                else:
                    # 未使用スロットは非表示
                    forced_updates.extend(
                        [gr.update(visible=False)] * components_per_arg
                    )

            self.logger.info(f"強制的args更新作成完了: {len(forced_updates)}個")
            return forced_updates

        except Exception as e:
            self.logger.error(f"強制的args更新作成エラー: {e}", exc_info=True)
            return []

    def _convert_params_to_elem_ids(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """パラメータをelem_id形式に変換（optimizer_args統合処理）

        Args:
            params: パラメータ辞書

        Returns:
            elem_id → 値のマッピング
        """
        elem_id_updates = {}

        for param_name, param_data in params.items():
            if param_name == "optimizer_args":
                # optimizer_argsは特別処理が必要なため、ここではスキップ
                # UI更新は_create_unified_update_dataで処理される
                continue
            else:
                # 通常パラメータ処理（既存ロジック継承）
                if isinstance(param_data, dict):
                    if "enabled" in param_data:
                        elem_id_updates[f"param-{param_name}-enabled"] = param_data[
                            "enabled"
                        ]
                    if "value" in param_data:
                        elem_id_updates[f"param-{param_name}-value"] = param_data[
                            "value"
                        ]

        return elem_id_updates

    def _create_component_update(self, component: Any, value: Any) -> Any:
        """コンポーネント種別に応じた更新データ作成

        Args:
            component: Gradioコンポーネント
            value: 設定する値

        Returns:
            Gradio更新データ
        """
        try:
            # Checkboxコンポーネントの場合
            if (
                hasattr(component, "__class__")
                and component.__class__.__name__ == "Checkbox"
            ):
                if isinstance(value, str):
                    value = value.lower() == "true"
                elif not isinstance(value, bool):
                    value = bool(value)

            # Numberコンポーネント（整数・浮動小数点）の場合
            elif hasattr(component, "precision") and component.precision is not None:
                if component.precision == 0:  # 整数
                    if isinstance(value, (int, float)):
                        value = int(value)
                    elif isinstance(value, str) and value.isdigit():
                        value = int(value)
                else:  # 浮動小数点
                    if isinstance(value, (int, float, str)):
                        try:
                            value = float(value)
                        except (ValueError, TypeError):
                            return gr.update()

            return gr.update(value=value)

        except Exception:
            return gr.update()

    def _create_error_response(self, component_count: int, error_message: str):
        """エラー時の空更新データを作成

        Args:
            component_count: コンポーネント数
            error_message: エラーメッセージ

        Returns:
            (エラーメッセージ, 空のプリセット名, *空更新データ)
        """
        empty_updates = [gr.update() for _ in range(component_count)]
        return (error_message, "", *empty_updates)
