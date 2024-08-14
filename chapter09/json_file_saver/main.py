import asyncio
import json
import os
from typing import Any, AsyncIterator, Iterator, Optional, Tuple

import aiofiles
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)


class JsonFileSaver(BaseCheckpointSaver):
    """jsonファイルにチェックポイントを保存するCheckpointSaver"""

    def __init__(self, file_path: str):
        """初期化メソッド"""
        super().__init__()
        self.file_path = file_path
        asyncio.run(self._ensure_file_exists())

    async def _ensure_file_exists(self):
        """ファイルが存在しない場合、空の辞書で初期化する"""
        if not os.path.exists(self.file_path):
            await self._write_data({})

    async def _read_data(self) -> dict[str, Any]:
        """jsonファイルからデータを読み込む"""
        max_retries = 3
        retry_delay = 0.1
        for attempt in range(max_retries):
            try:
                async with aiofiles.open(self.file_path, "r", encoding="utf-8") as f:
                    json_string = await f.read()
                    return self.serde.loads(json_string)
            except (IOError, json.JSONDecodeError) as e:
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    async def _write_data(self, data: dict[str, Any]):
        """jsonファイルにデータを書き込む"""
        async with aiofiles.open(self.file_path, "w", encoding="utf-8") as f:
            json_bytes: bytes = self.serde.dumps(data)
            await f.write(json_bytes.decode("utf-8"))

    def _create_checkpoint_tuple(
        self, thread_id: str, checkpoint_id: str, checkpoint_data: dict[str, Any]
    ) -> CheckpointTuple:
        """チェックポイントタプルを作成する"""
        return CheckpointTuple(
            config={
                "configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}
            },
            checkpoint=self.serde.loads(checkpoint_data["checkpoint"]),
            metadata=self.serde.loads(checkpoint_data["metadata"]),
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_data["parent_config"],
                    }
                }
                if checkpoint_data.get("parent_config")
                else None
            ),
            pending_writes=checkpoint_data.get("pending_writes", []),
        )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """チェックポイントタプルを取得する"""
        data = await self._read_data()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)

        if thread_id not in data:
            return None

        if checkpoint_id:
            checkpoint_data = data[thread_id].get(checkpoint_id)
        else:
            # 最新のチェックポイントを取得
            latest_checkpoint_id = max(data[thread_id].keys(), default=None)
            checkpoint_data = data[thread_id].get(latest_checkpoint_id)

        if checkpoint_data:
            return self._create_checkpoint_tuple(
                thread_id, checkpoint_id or latest_checkpoint_id, checkpoint_data
            )

        return None

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """チェックポイントを保存する"""
        data = await self._read_data()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        data.setdefault(thread_id, {})[checkpoint_id] = {
            "checkpoint": self.serde.dumps(checkpoint).decode("utf-8"),
            "metadata": self.serde.dumps(metadata).decode("utf-8"),
            "parent_config": config["configurable"].get("checkpoint_id"),
            "pending_writes": [],
        }
        await self._write_data(data)
        return {
            "configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """中間書き込みをチェックポイントに関連付けて保存する"""
        data = await self._read_data()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)
        checkpoint_data = data.get(thread_id, {}).get(checkpoint_id)
        if checkpoint_data:
            checkpoint_data.setdefault("pending_writes", []).extend(
                [
                    (task_id, channel, self.serde.dumps(value).decode("utf-8"))
                    for channel, value in writes
                ]
            )
            await self._write_data(data)

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """条件に合うチェックポイントをリストアップする

        thread_idが指定されている場合はそのthread_id内のみ、
        指定されていない場合は全てのデータを出力する。
        limitによる制限は有効。
        """
        data = await self._read_data()
        thread_id = config["configurable"]["thread_id"] if config else None

        # thread_idが指定されている場合はそのthread_idのみ
        # そうでない場合は全てのthread_idを対象とする
        thread_ids = [thread_id] if thread_id else data.keys()

        count = 0
        for tid in thread_ids:
            for cid, checkpoint_data in sorted(data[tid].items(), reverse=True):
                yield self._create_checkpoint_tuple(tid, cid, checkpoint_data)
                count += 1
                if limit is not None and count >= limit:
                    return

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return asyncio.run(self.aget_tuple(config))

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return asyncio.run(self.aput(config, checkpoint, metadata, new_versions))

    def put_writes(
        self,
        config: RunnableConfig,
        writes: list[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        asyncio.run(self.aput_writes(config, writes, task_id))

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        async def collect():
            return [
                checkpoint
                async for checkpoint in self.alist(
                    config, filter=filter, before=before, limit=limit
                )
            ]

        return asyncio.run(collect())


if __name__ == "__main__":
    from langchain_core.pydantic_v1 import BaseModel
    from langgraph.graph import StateGraph

    # グラフの状態を定義
    class State(BaseModel):
        count: int
        message: str

    # 簡単なノード関数を定義
    def increment_count(state: State) -> dict[str, Any]:
        return {"count": state.count + 1}

    def update_message(state: State) -> dict[str, Any]:
        return {"message": f"カウントは {state.count}"}

    # グラフを設定
    graph = StateGraph(State)
    graph.add_node("increment", increment_count)
    graph.add_node("update", update_message)

    graph.set_entry_point("increment")
    graph.add_edge("increment", "update")

    # チェックポインターを設定
    checkpointer = JsonFileSaver(file_path="tmp/checkpoint.json")

    # グラフをコンパイル
    compiled_graph = graph.compile(checkpointer=checkpointer)

    # グラフを実行
    config = {"configurable": {"thread_id": "example-thread"}}
    initial_state = State(count=0, message="initial")
    first_state = compiled_graph.invoke(initial_state, config)

    print("*** first_state ***")
    print(first_state)

    second_state = compiled_graph.invoke(first_state, config)

    print("*** second_state ***")
    print(second_state)

    # チェックポイントの取得
    result = checkpointer.get_tuple(config)
    if result:
        print(f"Checkpoint: {result.checkpoint}")
        print(f"Metadata: {result.metadata}")

    # チェックポイントのリスト
    for checkpoint_tuple in checkpointer.list(config):
        print(f"Listed Checkpoint: {checkpoint_tuple.checkpoint}")
        print(f"Listed Metadata: {checkpoint_tuple.metadata}")
