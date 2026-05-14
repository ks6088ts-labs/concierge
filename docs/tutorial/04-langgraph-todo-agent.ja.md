---
title: ステップ 4 - LangGraph Todo Agent CLI
description: Todo Web API をツール経由で操作する LangGraph ReAct エージェント CLI を実装する
---

# ステップ 4 - LangGraph Todo Agent CLI

## 概要

このステップでは `scripts/langgraph/vanilla.py` に
LangGraph + Microsoft Foundry の最小 CLI を追加します。

エージェントは Todo Web API をツール経由で呼び出し、次を実行できます。

- 単発実行: `run`
- 対話実行: `chat`

## 前提

別ターミナルで Todo API を起動します。

```bash
uv run todo-web
```

Microsoft Foundry の `.env` 設定は既存ステップと同様です。

## 使い方

### 単発実行

```bash
uv run python scripts/langgraph/vanilla.py run \
  --query "牛乳を買うタスクを追加して、その後一覧を見せて"
```

### 対話実行

```bash
uv run python scripts/langgraph/vanilla.py chat \
  --endpoint http://localhost:8000
```

共通オプション:

- `--endpoint/-e`: Todo API のベース URL（CLI > `TODO_API_ENDPOINT` > 既定値）
- `--model/-M`: `init_chat_model` に渡すモデル文字列
- `--timeout`: HTTP タイムアウト秒
- `--thread-id`: LangGraph の thread id

`chat` では `--system` でシステムプロンプトを上書きできます。

## スラッシュコマンド (`chat`)

- `/exit`, `/quit`: REPL を終了
- `/reset`: 会話 thread id を再採番
- `/help`: コマンドとツール一覧を表示
- `/tools`: ツールシグネチャ一覧を表示
- `/thread`: 現在の thread id を表示

## 観測性

`scripts/microsoft_foundry/vanilla.py` と同様に以下を利用できます。

- `--tracing/-t`: Azure Monitor / Foundry へのトレース
- `--mlflow/-m`: MLflow autologging
- `--verbose/-v`: DEBUG ログ

例:

```bash
uv run python scripts/langgraph/vanilla.py -t -m chat
```

## トラブルシューティング

Todo API が接続失敗や 4xx/5xx を返した場合、ツールは例外を送出せず
構造化エラー辞書を返します。エージェント側で再試行や自己修復が可能です。

確認ポイント:

1. `todo-web` が起動しているか
2. `--endpoint` が正しいか
3. `--verbose` で HTTP 詳細ログを確認
