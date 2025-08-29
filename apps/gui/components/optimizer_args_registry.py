"""
オプティマイザー引数のレジストリ
インデックスと引数名のマッピングを管理
"""

from typing import Any, Dict, List, Optional, Union

from core.presets.optimizer_template_manager import ArgumentConfig


class OptimizerArgsRegistry:
    """オプティマイザー引数のレジストリ

    インデックスベースのUIコンポーネントと
    識別子ベースのロジックをマッピングで接続
    """

    def __init__(self) -> None:
        """初期化"""
        self.index_to_name: Dict[int, str] = {}
        self.name_to_index: Dict[str, int] = {}
        self.index_to_config: Dict[int, ArgumentConfig] = {}
        self.current_optimizer: Optional[str] = None
        self.current_args: List[ArgumentConfig] = []

    def register_args(self, optimizer_type: str, args: List[ArgumentConfig]) -> None:
        """引数を登録

        Args:
            optimizer_type: オプティマイザータイプ
            args: 引数設定のリスト
        """
        self.current_optimizer = optimizer_type
        self.current_args = args
        self.index_to_name.clear()
        self.name_to_index.clear()
        self.index_to_config.clear()

        for idx, arg in enumerate(args):
            self.index_to_name[idx] = arg.name
            self.name_to_index[arg.name] = idx
            self.index_to_config[idx] = arg

    def get_elem_id(self, identifier: Union[int, str], component_type: str) -> str:
        """統一的なelem_id生成

        Args:
            identifier: インデックスまたは引数名
            component_type: コンポーネントタイプ

        Returns:
            elem_id文字列
        """
        # インデックスベースで統一（Gradioの制約対応）
        if isinstance(identifier, int):
            idx = identifier
        else:
            # 引数名からインデックスを取得
            idx = self.name_to_index.get(identifier, -1)
            if idx == -1:
                # 未登録の引数名の場合
                return f"opt-arg-unknown-{component_type}"

        return f"opt-arg-{idx}-{component_type}"

    def get_arg_name(self, index: int) -> Optional[str]:
        """インデックスから引数名を取得

        Args:
            index: インデックス

        Returns:
            引数名（見つからない場合はNone）
        """
        return self.index_to_name.get(index)

    def get_arg_index(self, name: str) -> Optional[int]:
        """引数名からインデックスを取得

        Args:
            name: 引数名

        Returns:
            インデックス（見つからない場合はNone）
        """
        return self.name_to_index.get(name)

    def get_arg_config(self, identifier: Union[int, str]) -> Optional[ArgumentConfig]:
        """引数設定を取得

        Args:
            identifier: インデックスまたは引数名

        Returns:
            引数設定（見つからない場合はNone）
        """
        if isinstance(identifier, int):
            return self.index_to_config.get(identifier)
        else:
            idx = self.name_to_index.get(identifier)
            if idx is not None:
                return self.index_to_config.get(idx)
        return None

    def extract_optimizer_args_from_elem_ids(
        self, elem_id_to_value: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """elem_idからオプティマイザー引数を抽出

        Args:
            elem_id_to_value: elem_id → 値のマッピング

        Returns:
            引数名 → {enabled, value}のマッピング
        """
        optimizer_args: Dict[str, Dict[str, Any]] = {}

        for elem_id, value in elem_id_to_value.items():
            if elem_id.startswith("opt-arg-"):
                # opt-arg-{index}-{type} の形式をパース
                parts = elem_id.replace("opt-arg-", "").rsplit("-", 1)
                if len(parts) == 2:
                    try:
                        idx = int(parts[0])
                        component_type = parts[1]

                        # インデックスから引数名と設定を取得
                        arg_name = self.index_to_name.get(idx)
                        arg_config = self.index_to_config.get(idx)

                        if not arg_name or not arg_config:
                            continue

                        if arg_name not in optimizer_args:
                            optimizer_args[arg_name] = {}

                        if component_type == "enabled":
                            optimizer_args[arg_name]["enabled"] = value
                        elif component_type in [
                            "text",
                            "number",
                            "dropdown",
                            "checkbox",
                        ]:
                            # 引数のUIタイプを取得
                            ui_type = arg_config.get_ui_component_type()

                            # UIタイプに対応するコンポーネントタイプかチェック
                            valid_component = False
                            if (
                                ui_type.value == "number_input"
                                and component_type == "number"
                            ):
                                valid_component = True
                            elif (
                                ui_type.value == "text_input"
                                and component_type == "text"
                            ):
                                valid_component = True
                            elif (
                                ui_type.value == "scientific_input"
                                and component_type == "text"
                            ):
                                valid_component = True
                            elif (
                                ui_type.value == "checkbox"
                                and component_type == "checkbox"
                            ):
                                valid_component = True
                            elif (
                                ui_type.value == "dropdown"
                                and component_type == "dropdown"
                            ):
                                valid_component = True

                            # 正しいコンポーネントタイプの値のみ処理
                            if valid_component and value is not None and value != "":
                                optimizer_args[arg_name]["value"] = value
                    except (ValueError, KeyError):
                        continue
        return optimizer_args

    def convert_optimizer_args_to_elem_ids(
        self, optimizer_args: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """オプティマイザー引数をelem_id形式に変換

        Args:
            optimizer_args: 引数名 → {enabled, value}のマッピング

        Returns:
            elem_id → 値のマッピング
        """
        elem_id_updates: Dict[str, Any] = {}

        for arg_name, arg_data in optimizer_args.items():
            idx = self.name_to_index.get(arg_name)
            if idx is None:
                continue

            if "enabled" in arg_data:
                elem_id = self.get_elem_id(idx, "enabled")
                elem_id_updates[elem_id] = arg_data["enabled"]

            if "value" in arg_data:
                # 引数設定から適切なコンポーネントタイプを決定
                arg_config = self.index_to_config.get(idx)
                if arg_config:
                    ui_type = arg_config.get_ui_component_type()

                    # UIタイプに応じたコンポーネントタイプ
                    if ui_type.value == "number_input":
                        component_type = "number"
                    elif ui_type.value == "text_input":
                        component_type = "text"
                    elif ui_type.value == "scientific_input":
                        component_type = "text"
                    elif ui_type.value == "dropdown":
                        component_type = "dropdown"
                    else:
                        component_type = "text"

                    elem_id = self.get_elem_id(idx, component_type)
                    elem_id_updates[elem_id] = arg_data["value"]

        return elem_id_updates

    def clear(self) -> None:
        """レジストリをクリア"""
        self.index_to_name.clear()
        self.name_to_index.clear()
        self.index_to_config.clear()
        self.current_optimizer = None
        self.current_args = []
