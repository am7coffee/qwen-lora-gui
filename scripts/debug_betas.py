"""betasが表示されない問題のデバッグ"""

from utils.optimizer_template_manager import OptimizerTemplateManager
from components.optimizer_ui_v3 import OptimizerUIV3

# テンプレート管理とUI作成
tm = OptimizerTemplateManager()
ui = OptimizerUIV3(tm)

print("=" * 80)
print("AdamW8bit betasのデバッグ")
print("=" * 80)

# AdamW8bitの引数を確認
config = tm.get_optimizer("AdamW8bit")
betas_arg = config.arguments[0]

print(f"引数名: {betas_arg.name}")
print(f"タイプ: {betas_arg.type}")
print(f"UIコンポーネント: {betas_arg.ui_component}")
print(f"UI決定タイプ: {betas_arg.get_ui_component_type()}")
print(f"デフォルト値: {betas_arg.default}")
print(f"ラベル: {betas_arg.labels}")
print()

# UI更新を取得
updates = ui.update_optimizer_ui("AdamW8bit")

print("UI更新内容:")
print(
    f"コンテナ visible: {updates[0].__dict__.get('visible') if hasattr(updates[0], '__dict__') else 'N/A'}"
)
print()

# betasの更新内容を詳細に確認（index 1-7）
print("betas引数のUI更新 (index 1-7):")
for i in range(1, 8):
    if i < len(updates):
        update = updates[i]
        if hasattr(update, "__dict__"):
            d = update.__dict__
            if d.get("visible"):
                print(f"  [{i}] visible=True")
                for key, value in d.items():
                    if key != "visible" and value is not None:
                        print(f"      {key}: {value}")
            else:
                print(f"  [{i}] visible=False")
        else:
            print(f"  [{i}] No __dict__")
print()

# _create_argument_ui_updatesメソッドを直接テスト
print("_create_argument_ui_updatesメソッドの直接テスト:")
arg_updates = ui._create_argument_ui_updates(betas_arg)
print(f"返される更新の数: {len(arg_updates)}")
for i, update in enumerate(arg_updates):
    if hasattr(update, "__dict__"):
        d = update.__dict__
        if d.get("visible"):
            print(f"  [{i}] visible=True - {d.get('label', 'no label')}")
        else:
            print(f"  [{i}] visible=False")
    else:
        print(f"  [{i}] No __dict__")
