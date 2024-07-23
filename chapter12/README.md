# エージェントデザインパターンサンプルソースコード

## 環境準備

1. 必要なライブラリをインストールします：
   ```
   pip install -r requirements.txt
   ```

2. .env.sampleをコピーし、.envファイルを作成します：
   ```
   cp .env.sample .env
   ```

3. .envファイル内の各キーにAPIキーを設定します
   ```
   OPENAI_API_KEY=your_api_key_here
   ANTHROPIC_API_KEY=your_api_key_here
   TAVILY_API_KEY=your_api_key_here
   ```

## 実行方法

### 1. Passive Goal Creator

```
python -m passive_goal_creator.main --task "明確化したいタスク"
```

### 2. Prompt Optimizer

```
python -m prompt_optimizer.main --task "明確化したいタスク"
```

### 3. Single Path Plan Generation

```
python -m single_path_plan_generation.main --task "実行したいタスク"
```

### 4. Multi Path Plan Generation

```
python -m multi_path_plan_generation.main --task "実行したいタスク"
```

### 5. Self Reflection

```
python -m self_reflection.main --task "実行したいタスク"
```

### 6. Cross Reflection

```
python -m cross_reflection.main --task "実行したいタスク"
```

### 7. Role based Cooperation

```
python -m role_based_cooperation.main --task "実行したいタスク"
```
