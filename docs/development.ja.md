---
title: 開発ガイド
description: concierge のローカルセットアップ、CLI 実行例、ドキュメント操作、Docker 操作
---

## ローカルセットアップ

開発依存関係をインストールし、環境変数テンプレートをコピーします。

```bash
make install-deps-dev
cp .env.template .env
```

`.env` に Microsoft Foundry project endpoint を設定します。

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>
MLFLOW_TRACKING_URI=http://127.0.0.1:5000
```

Foundry へ接続する前に Azure CLI でサインインします。

```bash
az login
```

## サンプル CLI

利用できる Typer コマンドは help で確認できます。

```bash
uv run python scripts/microsoft_foundry/vanilla.py --help
```

代表的な実行例です。

```bash
uv run python scripts/microsoft_foundry/vanilla.py hello-world \
    --query "Summarize LangChain in one sentence."

uv run python scripts/microsoft_foundry/vanilla.py use-in-agents \
    --query "Explain why observability matters for LLM applications."

uv run python scripts/microsoft_foundry/vanilla.py vector-store-search \
    --query thud --k 1
```

グローバルオプションで observability を有効化できます。

* `--tracing` は Microsoft Foundry / Azure Monitor tracing に LangChain run を送信します。
* `--mlflow` は MLflow の LangChain autologging を有効化します。
* `--verbose` はローカル logger を `DEBUG` にします。

`--mlflow` を使う場合は、別ターミナルでローカル MLflow UI を起動します。

```bash
make mlflow
```

## 開発コマンド

よく使う操作は Makefile target にまとめています。

```bash
# 利用可能な make target を表示します。
make

# テストを実行します。
make test

# format check、lint、test をまとめて実行します。
make ci-test

# docs 依存関係のインストールと site build をまとめて実行します。
make ci-test-docs

# ドキュメントをビルドします。
make docs

# ドキュメントをローカルプレビューします。
make docs-serve
```

Docker image のビルドと実行も Makefile から行えます。

```bash
make docker-build
make docker-run
```

## GitHub Pages

[github-pages workflow](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml) は、`main` ブランチから `mkdocs gh-deploy --force` で MkDocs site をデプロイします。

* [公開ドキュメント](https://ks6088ts-labs.github.io/concierge/)
* [日本語版ドキュメント](https://ks6088ts-labs.github.io/concierge/ja/)
* [ハンズオンチュートリアル](https://ks6088ts-labs.github.io/concierge/tutorial/)
