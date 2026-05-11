---
title: concierge
description: Microsoft Foundry, LangChain, and LangGraph hands-on examples with observability
---

[![test](https://github.com/ks6088ts-labs/concierge/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/ks6088ts-labs/concierge/actions/workflows/test.yaml?query=branch%3Amain)
[![docker](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker.yaml/badge.svg?branch=main)](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker.yaml?query=branch%3Amain)
[![docker-release](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker-release.yaml/badge.svg)](https://github.com/ks6088ts-labs/concierge/actions/workflows/docker-release.yaml)
[![ghcr-release](https://github.com/ks6088ts-labs/concierge/actions/workflows/ghcr-release.yaml/badge.svg)](https://github.com/ks6088ts-labs/concierge/actions/workflows/ghcr-release.yaml)
[![docs](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml/badge.svg)](https://github.com/ks6088ts-labs/concierge/actions/workflows/github-pages.yaml)

## 概要

`concierge` は、Microsoft Foundry 上のモデルを LangChain / LangGraph から扱うための Python ハンズオンリポジトリです。Foundry の chat、agent、embedding、vector store、observability を Typer CLI と MkDocs チュートリアルで試せます。

## 前提条件

ローカル開発には次のツールを使います。

* [Python 3.10+](https://www.python.org/downloads/)
* [uv](https://docs.astral.sh/uv/getting-started/installation/)
* [GNU Make](https://www.gnu.org/software/make/)

Foundry のサンプル CLI を実行する場合は、追加で次の準備が必要です。

* Microsoft Foundry project
* Foundry project にデプロイ済みの chat model と embedding model
* [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) での `az login`

## 導線

詳細なセットアップ、CLI の実行例、開発コマンドは GitHub Pages にまとめています。

* [concierge documentation](https://ks6088ts-labs.github.io/concierge/)
* [日本語版ドキュメント](https://ks6088ts-labs.github.io/concierge/ja/)
* [ハンズオンチュートリアル](https://ks6088ts-labs.github.io/concierge/tutorial/)
* [開発ガイド](https://ks6088ts-labs.github.io/concierge/development/)

`main` ブランチへの push で [github-pages workflow](.github/workflows/github-pages.yaml) が実行され、Pages が更新されます。
