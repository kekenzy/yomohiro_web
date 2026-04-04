# ドキュメント索引

リポジトリ内の Markdown を目的別に整理した入口です。新規参加者は **README → 本番なら PRODUCTION / DEPLOYMENT** の順が読みやすいです。

---

## すぐ読む順（おすすめ）

| 順 | ドキュメント | 誰向け | 内容 |
|----|----------------|--------|------|
| 1 | [README.md](README.md) | 全員 | 概要・ローカル／Docker セットアップ |
| 2 | [PRODUCTION.md](PRODUCTION.md) | 運用・本番 | **本番の環境変数・LINE / Square・migrate 等** |
| 3 | [DEPLOYMENT.md](DEPLOYMENT.md) | 本番デプロイ | Lightsail・GitHub Actions・初期サーバ設定 |
| 4 | [SSL_SETUP.md](SSL_SETUP.md) | 本番 | HTTPS（Let's Encrypt 等） |

---

## 全ドキュメント一覧

| ファイル | 概要 |
|----------|------|
| [README.md](README.md) | プロジェクト説明、セットアップ、基本構造 |
| [DOCUMENTATION.md](DOCUMENTATION.md) | 本ファイル（索引） |
| [PRODUCTION.md](PRODUCTION.md) | **本番環境の設定**（環境変数、LINE、付帯作業） |
| [DEPLOYMENT.md](DEPLOYMENT.md) | AWS Lightsail デプロイ、GitHub Secrets、ドメイン・SSL 手順への言及 |
| [SSL_SETUP.md](SSL_SETUP.md) | Let's Encrypt 前提条件と証明書取得手順 |
| [LIGHTSAIL_NETWORK_SETUP.md](LIGHTSAIL_NETWORK_SETUP.md) | Lightsail のファイアウォール・ポート等 |
| [SQUARE_PAYMENT_FLOW.md](SQUARE_PAYMENT_FLOW.md) | Square API と会員登録・決済の流れ（技術） |
| [SQUARE_ENVIRONMENT_SETUP.md](SQUARE_ENVIRONMENT_SETUP.md) | Square の sandbox / production 切り替え |
| [FEATURES.md](FEATURES.md) | 機能一覧と主要ファイルの対応（開発者向け） |
| [ADMIN_CREDENTIALS.md](ADMIN_CREDENTIALS.md) | 管理画面アカウントに関する注意（機密の取り扱い） |

---

## テーマ別

### 本番サーバ・公開

- 全体の流れ: [DEPLOYMENT.md](DEPLOYMENT.md)
- **環境変数・LINE・migrate**: [PRODUCTION.md](PRODUCTION.md)
- HTTPS: [SSL_SETUP.md](SSL_SETUP.md)、[DEPLOYMENT.md](DEPLOYMENT.md) の SSL 節
- ネットワーク: [LIGHTSAIL_NETWORK_SETUP.md](LIGHTSAIL_NETWORK_SETUP.md)

### 決済・外部サービス

- Square: [SQUARE_PAYMENT_FLOW.md](SQUARE_PAYMENT_FLOW.md)、[SQUARE_ENVIRONMENT_SETUP.md](SQUARE_ENVIRONMENT_SETUP.md)
- LINE Login: [PRODUCTION.md](PRODUCTION.md) の「LINE Login」

### 開発・仕様把握

- 機能とコードの対応: [FEATURES.md](FEATURES.md)
- 初期セットアップ: [README.md](README.md)

---

## メンテナンスメモ

- 新しい `.md` をルートに追加したら、**本ファイルの「全ドキュメント一覧」に 1 行追加**すると索引がずれません。
- 本番の秘密情報は **Markdown に実値を書かない**（プレースホルダまたは変数名のみ）。
