"""
オプティマイザーテンプレートローダー
templates/optimizer_templates.jsonからオプティマイザー定義を読み込む
"""

import json
import os
from typing import Dict, Any, Optional


class OptimizerTemplateLoader:
    """オプティマイザーテンプレートローダークラス"""

    def __init__(
        self,
        template_path: str = "data/config/templates/optimizer_templates.json",
    ):
        """
        Args:
            template_path: テンプレートファイルのパス
        """
        self.template_path = template_path
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Any]:
        """テンプレートファイルを読み込む"""
        if not os.path.exists(self.template_path):
            # ファイルが存在しない場合はデフォルトテンプレートを返す
            return self._get_default_templates()

        try:
            with open(self.template_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # 読み込みエラーの場合はデフォルトテンプレートを返す
            return self._get_default_templates()

    def _get_default_templates(self) -> Dict[str, Any]:
        """デフォルトテンプレートを返す"""
        return {
            "AdamW8bit": {
                "display_name": "AdamW8bit (メモリ効率)",
                "description": "8bit量子化によりメモリ使用量を削減したAdamW",
                "args": {
                    "betas": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "(0.9, 0.999)",
                        "description": "モーメンタム係数",
                        "placeholder": "(0.9, 0.999)",
                    },
                    "eps": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "1e-8",
                        "description": "数値安定性用イプシロン",
                        "placeholder": "1e-8",
                    },
                    "weight_decay": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "0.01",
                        "description": "重み減衰",
                        "placeholder": "0.01",
                    },
                    "amsgrad": {
                        "type": "str",
                        "ui_element": "Dropdown",
                        "default": "false",
                        "choices": ["true", "false"],
                        "description": "AMSGrad使用",
                    },
                },
            },
            "prodigyopt.Prodigy": {
                "display_name": "Prodigy (推奨)",
                "description": "自動学習率調整オプティマイザー。LoRA学習に最適",
                "args": {
                    "betas": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "(0.9, 0.99)",
                        "description": "モーメンタム係数",
                        "placeholder": "(0.9, 0.99)",
                    },
                    "d_coef": {
                        "type": "str",
                        "ui_element": "Textbox",
                        "default": "2.0",
                        "description": "D係数",
                        "placeholder": "2.0",
                    },
                    "use_bias_correction": {
                        "type": "str",
                        "ui_element": "Dropdown",
                        "default": "true",
                        "choices": ["true", "false"],
                        "description": "バイアス補正",
                    },
                },
            },
        }

    def get_optimizer_list(self) -> list:
        """利用可能なオプティマイザーのリストを返す"""
        return list(self.templates.keys())

    def get_optimizer_info(self, optimizer_type: str) -> Optional[Dict[str, Any]]:
        """指定されたオプティマイザーの情報を返す"""
        if optimizer_type not in self.templates:
            return None

        template = self.templates[optimizer_type]
        return {
            "display_name": template.get("display_name", optimizer_type),
            "description": template.get("description", ""),
        }

    def get_optimizer_args(self, optimizer_type: str) -> Optional[Dict[str, Any]]:
        """指定されたオプティマイザーの引数定義を返す"""
        if optimizer_type not in self.templates:
            return None

        return self.templates[optimizer_type].get("args", {})
