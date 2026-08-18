from __future__ import annotations

from qdrant_client import QdrantClient, models

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "day6_qdrant_demo"


def main() -> None:
    client = QdrantClient(url=QDRANT_URL)

    # 为了保证smoke test每次运行结果一致
    # 如果之前存在测试collection，就先删除
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(collection_name=COLLECTION_NAME)

    # 1.创建collection
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=4,
            distance=models.Distance.COSINE,
        ),
    )

    print("Collection 创建成功")

    # 2.写入Points
    client.upsert(
        collection_name=COLLECTION_NAME,
        wait=True,
        points=[
            models.PointStruct(
                id=1,
                vector=[1.0, 0.0, 0.0, 0.0],
                payload={
                    "title": "EPICS",
                    "system": "EPICS",
                },
            ),
            models.PointStruct(
                id=2,
                vector=[0.8, 0.2, 0.0, 0.0],
                payload={
                    "title": "IOC",
                    "system": "EPICS",
                },
            ),
        ],
    )

    print("Points 写入成功")

    # 3.Top-k查询
    query_result = client.query_points(
        collection_name=COLLECTION_NAME,
        query=[1.0, 0.0, 0.0, 0.0],
        limit=3,
        with_payload=True,
    )

    print("\n查询结果")

    for rank, point in enumerate(query_result.points, start=1):
        print(
            rank,
            point.id,
            point.score,
            point.payload,
        )

    # 4.删除一个point
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=models.PointIdsList(
            points=[1],
        ),
        wait=True,
    )

    print("\nPoint 1 删除成功")

    # 5. 再次查询
    query_after_delete = client.query_points(
        collection_name=COLLECTION_NAME,
        query=[1.0, 0.0, 0.0, 0.0],
        limit=3,
        with_payload=True,
    )

    print("\n删除后的查询结果")

    for rank, point in enumerate(
        query_after_delete.points,
        start=1,
    ):
        print(
            rank,
            point.id,
            point.score,
            point.payload,
        )


if __name__ == "__main__":
    main()
