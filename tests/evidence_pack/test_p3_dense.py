from accelerator_rag.evidence_pack.dense import EmbeddingDenseChannel, HashingEmbedder

from conftest import FakeChunk


def test_hashing_dense_channel_ranks_matching_chunk():
    chunks = [
        FakeChunk("c1", "rev-a", "端口 45-48 分配给系统甲 VLAN9"),
        FakeChunk("c2", "rev-a", "无关的页面内容"),
    ]
    channel = EmbeddingDenseChannel.hashing(chunks)
    hits = channel.search("45-48 端口 VLAN9", [chunk.chunk_id for chunk in chunks], 2)
    assert hits[0][0] == "c1"
    assert channel.available is True
    assert isinstance(HashingEmbedder(16).embed("测试"), tuple)
