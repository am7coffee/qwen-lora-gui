"""
コマンド生成関連の共有機能

両システム（GUI・queue）で使用されるコマンド生成ロジックを提供
"""

from .command_generator import CommandGenerator

__all__ = ["CommandGenerator"]
