"""
パラメータ定義・設定管理の共有機能

アプリケーション全体で使用される設定値とパラメータ定義を提供
"""

# 後方互換性のためのre-export
from .parameters import get_all_parameters, ParameterConfig
from .optimizer_templates import OptimizerTemplateLoader, get_optimizer_template_loader
from .path_resolver import PathResolver

__all__ = [
    "get_all_parameters",
    "ParameterConfig",
    "OptimizerTemplateLoader",
    "get_optimizer_template_loader",
    "PathResolver",
]
