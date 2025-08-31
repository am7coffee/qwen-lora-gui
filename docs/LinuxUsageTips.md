# Linux利用Tips

## GUI、キューシステムのLinux対応について

### 起動設定

#### ホスト、シェア設定（--host）(--share)

```bash
python launch_gui.py --host 0.0.0.0 --share
python launch_queue.py --host 0.0.0.0 --share
```

#### クラウド環境でのGradio Live利用

起動時のターミナル画面にGradio Liveの公開URLが表示されます。

**GUIアプリ起動時の表示例:**

```
=== Application Starting ===
Running execution file cleanup...
Cleanup target directory: D:\Musubi\qwen-lora-gui\data\logs\executions
No sh files to delete
tmux not found. Skipping tmux session cleanup.
=== Cleanup Completed ===

Running on local URL:  http://0.0.0.0:7860
Running on public URL: https://xxxxxxxxxxxxxxxx.gradio.live
```

**キューシステム起動時の表示例:**

```
==========================================================
Qwen LoRA GUI - Queue System
==========================================================
Local URL: http://0.0.0.0:7862
共有URLを生成中...

Running on local URL:  http://0.0.0.0:7862
Running on public URL: https://xxxxxxxxxxxxxxxx.gradio.live
```

> **注意:** クラウド提供業者によってGradio Live利用が許可されているかは各自でご確認ください。
> 公開URLは72時間有効で、外部からアクセス可能です。

クラウド環境でGradio Liveを使用する場合、キューシステムの設定ファイルを変更する必要があります。

**設定ファイル:** `data/config/queue_config.json`

```json
{
  "queue_system": {
    "default_port": 7862,
    "host": "127.0.0.1",
    "auto_open": true,
    "enable_share": true,  // クラウド環境ではtrueに変更
    "share_host": "0.0.0.0",
    "description": "キューシステムのデフォルト設定"
  }
}
```

- **ローカル環境**: `"enable_share": false` 推奨
- **クラウド環境**: `"enable_share": true` 必須

---

## Linux稼働時の動作仕様

### コマンド実行方式

Linux環境では標準出力でコマンドを実行します。

### ログ出力先

実行ログは以下のディレクトリに出力されます：

```
data/logs/executions/
```

---

## プロセス強制停止（Linux）

タスクが正常に停止しない場合は、ターミナルから直接プロセスを終了してください。

### 潜在変数キャッシュ生成の停止

```bash
# プロセス確認
ps aux | grep qwen_image_cache_latents

# 停止
pkill -f "qwen_image_cache_latents.py"
```

### TEキャッシュ生成の停止

```bash
# プロセス確認
ps aux | grep qwen_image_cache_text_encoder

# 停止
pkill -f "qwen_image_cache_text_encoder_outputs.py"
```

### 学習プロセスの停止

```bash
# 学習プロセス確認
ps aux | grep -E "(train\.py|lora_train)"

# 停止
pkill -f "train.py"
```

---

## 補足事項

- プロセス確認は必ず停止前に実行することを推奨します
- `pkill`コマンドを使用する際は、対象プロセスが正しいことを確認してから実行してください
- 複数のプロセスが動作している場合は、PIDを指定した個別停止も可能です：

```bash
# PIDを指定した停止
kill <PID>

# 強制終了
kill -9 <PID>
```