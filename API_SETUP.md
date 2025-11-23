# Claude API 設定ガイド

Claude Code Voice Controllerは、Claude APIを使用してセッション出力を自動要約します。

## セットアップ手順

### 1. APIキーの取得

1. [Anthropic Console](https://console.anthropic.com/)にアクセス
2. アカウントを作成またはログイン
3. API Keys セクションで新しいAPIキーを生成
4. APIキーをコピー（`sk-ant-api03-` で始まる文字列）

### 2. 設定ファイルの作成

```bash
# サンプルファイルをコピー
cp api_config.json.example api_config.json
```

### 3. APIキーの設定

`api_config.json`を開いて、`anthropic_api_key`にあなたのAPIキーを設定：

```json
{
  "anthropic_api_key": "sk-ant-api03-YOUR-API-KEY-HERE",
  "model": "claude-sonnet-4-5-20250929",
  "max_tokens": 200,
  "temperature": 0.7,
  "summary_instructions": "以下のClaude Codeセッションの出力を、10秒で読める程度（約150文字）に要約してください。重要なポイント、エラー、進捗状況を含めてください。"
}
```

### 4. 設定項目の説明

| 項目 | 説明 | デフォルト値 |
|------|------|-------------|
| `anthropic_api_key` | Anthropic APIキー | 必須 |
| `model` | 使用するClaudeモデル | `claude-sonnet-4-5-20250929` |
| `max_tokens` | 要約の最大トークン数 | `200` |
| `temperature` | 生成の温度（0-1） | `0.7` |
| `summary_instructions` | 要約時の指示文 | カスタマイズ可能 |

## APIなしでの動作

APIキーが設定されていない場合、システムは自動的にフォールバック（簡易要約）モードで動作します。

- ✅ 基本的な機能は全て利用可能
- ⚠️ 要約の質がAI要約より劣る
- ℹ️ API使用料金が発生しない

## セキュリティ

**重要**: `api_config.json`ファイルには機密情報（APIキー）が含まれます。

- ✅ `.gitignore`に追加済み（gitにコミットされません）
- ⚠️ このファイルを他人と共有しないでください
- ⚠️ 公開リポジトリにプッシュしないでください

## トラブルシューティング

### エラー: "API config file not found"

```bash
# サンプルファイルが存在するか確認
ls api_config.json.example

# 設定ファイルを作成
cp api_config.json.example api_config.json
```

### エラー: "API key not configured"

`api_config.json`の`anthropic_api_key`を実際のAPIキーに置き換えてください。

### エラー: "API summarization failed"

1. APIキーが正しいか確認
2. インターネット接続を確認
3. Anthropic APIの状態を確認: https://status.anthropic.com/

エラーが発生した場合、システムは自動的にフォールバックモードに切り替わります。

## コスト

Claude API Sonnet 4.5の料金（2025年1月時点）:
- 入力: $3.00 / million tokens
- 出力: $15.00 / million tokens

要約1回あたりの推定コスト:
- 入力: 最大10,000文字 ≈ 2,500トークン → $0.0075
- 出力: 最大200トークン → $0.003
- **合計: 約 $0.01 / 要約**

セッションが3つあり、2秒ごとに更新される場合：
- 1時間で約5,400回の要約
- コスト: 約$54/時間

**推奨**:
- `UPDATE_INTERVAL`を長めに設定（例: 5秒 → 5000ms）
- 要約を手動トリガーに変更（今後の機能追加で対応予定）
