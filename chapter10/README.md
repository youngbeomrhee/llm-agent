# 要件定義書生成AIエージェントの使用方法

## 環境準備

1. 必要なライブラリをインストールします：
   ```
   pip install -r requirements.txt
   ```

2. .env.sampleをコピーし、.envファイルを作成します：
   ```
   cp .env.sample .env
   ```

3. .envファイル内のOPENAI_API_KEYにOpenAIのAPIキーを設定します：
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## 実行方法

以下のコマンドを実行すると、要件定義書生成AIエージェントが起動し、指定されたタスクに基づいてドキュメントを生成します：

```
python -m documentation_agent.main --task "要件定義したいアプリの内容"
```

例：
```
python -m documentation_agent.main --task "マッチングアプリ"
```

## 注意事項

- APIの使用量に注意してください。大量のコードを処理する場合、OpenAI APIの使用コストが増加する可能性があります。