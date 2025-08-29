"""
オプティマイザーテンプレート管理システム
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple


class OptimizerTemplateLoader:
    """オプティマイザーテンプレートローダークラス"""

    def __init__(self, templates_dir: str = "data/config/templates"):
        self.templates_dir = templates_dir
        self.templates_file = os.path.join(templates_dir, "optimizer_templates.json")
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Any]:
        """テンプレートファイルを読み込み"""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            else:
                print(f"Warning: Template file not found: {self.templates_file}")
                return self._get_fallback_templates()
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in template file: {e}")
            return self._get_fallback_templates()
        except Exception as e:
            print(f"Error loading templates: {e}")
            return self._get_fallback_templates()

    def _get_fallback_templates(self) -> Dict[str, Any]:
        """フォールバック用デフォルトテンプレート"""
        return {
            "prodigyopt.Prodigy": {
                "display_name": "Prodigy (推奨)",
                "description": "自動学習率調整オプティマイザー",
                "args": {
                    "lr": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "1.0",
                        "description": "学習率",
                        "placeholder": "1.0",
                    },
                    "d0": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "1e-6",
                        "description": "D推定初期値",
                        "placeholder": "1e-6",
                    },
                },
            },
            "AdamW": {
                "display_name": "AdamW (標準)",
                "description": "PyTorch標準のAdamW",
                "args": {
                    "lr": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "1e-3",
                        "description": "学習率",
                        "placeholder": "1e-3",
                    }
                },
            },
        }

    def get_optimizer_list(self) -> List[Tuple[str, str]]:
        """オプティマイザー一覧を取得（ドロップダウン用）"""
        optimizer_list = []
        for optimizer_type, template in self.templates.items():
            display_name = template.get("display_name", optimizer_type)
            optimizer_list.append((display_name, optimizer_type))
        return optimizer_list

    def get_optimizer_choices(self) -> List[str]:
        """オプティマイザー選択肢を取得（値のみ）"""
        return list(self.templates.keys())

    def get_optimizer_display_choices(self) -> List[str]:
        """オプティマイザー表示名選択肢を取得"""
        return [
            template.get("display_name", optimizer_type)
            for optimizer_type, template in self.templates.items()
        ]

    def get_optimizer_template(self, optimizer_type: str) -> Optional[Dict[str, Any]]:
        """指定オプティマイザーのテンプレートを取得"""
        return self.templates.get(optimizer_type)

    def get_optimizer_args(self, optimizer_type: str) -> Dict[str, Any]:
        """指定オプティマイザーの引数定義を取得"""
        template = self.get_optimizer_template(optimizer_type)
        if template and isinstance(template, dict):
            args = template.get("args", {})
            return args if isinstance(args, dict) else {}
        return {}

    def get_optimizer_description(self, optimizer_type: str) -> str:
        """指定オプティマイザーの説明を取得"""
        template = self.get_optimizer_template(optimizer_type)
        if template and isinstance(template, dict):
            desc = template.get("description", "")
            return desc if isinstance(desc, str) else ""
        return ""

    def validate_template_structure(self, template_data: Dict[str, Any]) -> bool:
        """テンプレートデータの構造を検証"""
        try:
            for optimizer_type, optimizer_data in template_data.items():
                if not isinstance(optimizer_data, dict):
                    return False

                # 必須フィールドの確認
                if "args" not in optimizer_data:
                    return False

                args = optimizer_data["args"]
                if not isinstance(args, dict):
                    return False

                # 各引数の構造確認
                for arg_name, arg_config in args.items():
                    if not isinstance(arg_config, dict):
                        return False

                    required_fields = ["type", "ui_element", "default", "description"]
                    for field in required_fields:
                        if field not in arg_config:
                            return False

            return True
        except Exception:
            return False

    def reload_templates(self) -> bool:
        """テンプレートファイルを再読み込み"""
        try:
            self.templates = self._load_templates()
            return True
        except Exception as e:
            print(f"Error reloading templates: {e}")
            return False

    def get_template_file_path(self) -> str:
        """テンプレートファイルのパスを取得"""
        return self.templates_file

    def is_template_file_exists(self) -> bool:
        """テンプレートファイルが存在するかチェック"""
        return os.path.exists(self.templates_file)

    def get_optimizer_count(self) -> int:
        """定義されているオプティマイザー数を取得"""
        return len(self.templates)


# グローバルインスタンス（シングルトンパターン）
_optimizer_template_loader = None


def get_optimizer_template_loader() -> OptimizerTemplateLoader:
    """オプティマイザーテンプレートローダーのグローバルインスタンスを取得"""
    global _optimizer_template_loader
    if _optimizer_template_loader is None:
        _optimizer_template_loader = OptimizerTemplateLoader()
    return _optimizer_template_loader
