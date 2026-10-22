# Stage 2.7 Embedding 模型受控比较

所有小样本指标仅作诊断（diagnostic only）。完整 Top-5 父 Chunk、获胜 passage、分数和证据组判断见同名 JSON。

## 实验边界

固定 13 份 PDF、pdf-chunks-v3、资格策略、21 条可回答查询、11 条负例和 evidence-contract-v1。固定 cosine、passage policy 和 parent max-child 聚合。不同模型的 cosine 绝对值不横向比较。

## 工程修正

`index_document()` 替换指定文档并保留其他文档。`index_corpus()` 验证完整 corpus。两个 store 只共享 collection 基础能力。持久化回归测试验证重开、stale 清理、其他文档的 payload/vector 不变及编码次数。模型指纹逐块计算权重 SHA-256。

## 总体指标

Model | Hit@1 | Hit@3 | Hit@5 | MRR@5
--- | ---: | ---: | ---: | ---:
BAAI/bge-small-zh-v1.5 | 0.0952 | 0.2381 | 0.4286 | 0.2040
intfloat/multilingual-e5-base | 0.2857 | 0.6190 | 0.7619 | 0.4778
BAAI/bge-base-zh-v1.5 | 0.0952 | 0.4286 | 0.6190 | 0.2754

## BAAI/bge-small-zh-v1.5

### 身份和成本

```json
{
  "fingerprint": {
    "requested_model_name": "BAAI/bge-small-zh-v1.5",
    "resolved_local_model_path": "/home/whloong/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620",
    "local_snapshot_id": "7999e1d3359715c523056ef9478215996d62a620",
    "snapshot_identity_source": "local cache path",
    "model_config_sha256": "3853a7979202c348751b753e36f579c41d8da7d36af617d3d907e1fc9b441f2a",
    "config_files": {
      "1_Pooling/config.json": "aaa8861589f80c961a03cc86c7eeaef7605c1676b9ab55329d33a304738769c6",
      "config.json": "3853a7979202c348751b753e36f579c41d8da7d36af617d3d907e1fc9b441f2a",
      "config_sentence_transformers.json": "940d5f50db195fa6e5e6a4f122c095f77880de259d74b14a65779ed48bdd7c56",
      "modules.json": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
      "sentence_bert_config.json": "84e39fda68ccbff05bfa723ae9c0e70e23e2ec373b76e0f8c6e71af72a693cbf",
      "special_tokens_map.json": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
      "tokenizer.json": "48cea5d44424912a6fd1ea647bf4fe50b55ab8b1e5879c3275f80e339e8fae26",
      "tokenizer_config.json": "e6f3b96db926a37d4039995fbf5ad17de158dfb8f6343d607e4dbaad18d75f5a"
    },
    "tokenizer_sha256": "838bba27a9e5bbcbb7bed0b25535c69d88b63768857dda2ab13d015c4a98591f",
    "weights_files": {
      "model.safetensors": "354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026"
    },
    "weights_manifest_sha256": "e8a74ff510b7bb678d388e28bed644b00f003bac55dd1e718dc1079ea89255e5",
    "max_seq_length": 512,
    "dimension": 512,
    "query_template": "为这个句子生成表示以用于检索相关文章：{query}",
    "document_prefix": "",
    "local_model_bytes": 96405966
  },
  "passage_statistics": {
    "algorithm": "dense-passages-v1",
    "contract": {
      "algorithm": "dense-passages-v1",
      "config": {
        "max_tokens": null,
        "guard_tokens": 16,
        "overlap_tokens": 32
      },
      "tokenizer": {
        "model": "BAAI/bge-small-zh-v1.5",
        "max_seq_length": 512,
        "tokenizer_sha256": "838bba27a9e5bbcbb7bed0b25535c69d88b63768857dda2ab13d015c4a98591f",
        "do_lower_case": true,
        "template": "document_title + \"\\n\" + passage.text"
      },
      "effective_max_tokens": 512
    },
    "contract_id": "1041a9bee3f5fcffa7dd72f0ae62a59a2e39b9aca6c72450087f4e5e87733595",
    "model_max_seq_length": 512,
    "eligible_parent_chunks": 4532,
    "embedding_passages": 4950,
    "parents_with_1_passage": 4156,
    "parents_split": 376,
    "average_passages_per_parent": 1.0922330097087378,
    "passages_per_parent": {
      "count": 4532,
      "min": 1,
      "max": 4,
      "mean": 1.0922330097087378,
      "p10": 1.0,
      "p25": 1.0,
      "median": 1.0,
      "p75": 1.0,
      "p90": 1.0,
      "p95": 2.0
    },
    "passage_token_length": {
      "count": 4950,
      "min": 8,
      "max": 512,
      "mean": 315.5387878787879,
      "p10": 149.0,
      "p25": 232.0,
      "median": 334.0,
      "p75": 399.0,
      "p90": 463.0,
      "p95": 483.0
    },
    "passages_exceeding_limit": 0,
    "all_passage_inputs_within_model_limit": true,
    "guard_policy": "Already-fitting parent inputs remain unchanged; split windows reserve guard_tokens in the complete title+body+specials template.",
    "by_document": {
      "epics-application-developers-guide-r3-16-2": {
        "parents": 847,
        "passages": 858
      },
      "epics-documentation-latest-2026-08-18": {
        "parents": 1071,
        "passages": 1086
      },
      "european-xfel-full-technical-design-report-2007": {
        "parents": 1730,
        "passages": 1780
      },
      "european-xfel-standard-e-beam-diagnostics-linac2010": {
        "parents": 13,
        "passages": 13
      },
      "european-xfel-undulator-commissioning-spectrometer-cdr-2011": {
        "parents": 41,
        "passages": 41
      },
      "european-xfel-x-ray-optics-beam-transport-tdr-2012": {
        "parents": 235,
        "passages": 246
      },
      "shine-accelerator-control-system-design-presentation": {
        "parents": 33,
        "passages": 33
      },
      "shine-accelerator-fast-interlock-2024": {
        "parents": 18,
        "passages": 27
      },
      "shine-accelerator-preliminary-design-report-2017": {
        "parents": 477,
        "passages": 799
      },
      "shine-control-system-status-icalepcs2019": {
        "parents": 15,
        "passages": 15
      },
      "shine-cryogenic-control-system-2021": {
        "parents": 22,
        "passages": 22
      },
      "shine-epics-ioc-pv-information-management-pcapac2022": {
        "parents": 13,
        "passages": 13
      },
      "shine-white-rabbit-beam-synchronous-timing-ipac2022": {
        "parents": 17,
        "passages": 17
      }
    }
  },
  "collection": "knowledge_stage27_baai__bge_small_zh_v1.5",
  "qdrant_path": "tmp/stage-two-seven/baai--bge-small-zh-v1.5/qdrant",
  "timing": {
    "model_load_seconds": 2.351859399001114,
    "fingerprint_seconds": 0.08204333700996358,
    "passage_preparation_seconds": 2.8750322190026054,
    "embedding_seconds": 0,
    "qdrant_indexing_seconds": 0,
    "point_count": 4950,
    "embedded_passage_count": 0,
    "unique_parent_count": 4532,
    "evaluation_seconds": 0.7381150769942906
  },
  "vectors_reused": true,
  "historical_control_embedding_seconds": 524.8550086799769,
  "control_reuse_note": "Identical passage IDs/content/canonical parents verified against Stage 2.6; query rankings/metrics revalidated. Current local weights fingerprint recorded now; historical report had no weights fingerprint, so byte identity at the historical run cannot be proved retrospectively.",
  "first_build_timing": {
    "model_load_seconds": 2.292060677005793,
    "fingerprint_seconds": 0.07774024299578741,
    "passage_preparation_seconds": 2.8184781890013255,
    "embedding_seconds": 0,
    "qdrant_indexing_seconds": 10.254786606994458,
    "point_count": 4950,
    "embedded_passage_count": 0,
    "unique_parent_count": 4532,
    "evaluation_seconds": 0.7165280949993758
  },
  "encoding_contract_source": {
    "local_path": "/home/whloong/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/7999e1d3359715c523056ef9478215996d62a620/README.md",
    "sha256": "c48a4eeea77f6b1d38b48ec1c5b8d4f86d5550cc43fa345a0db1b2ca1d082369",
    "publisher_url": "https://huggingface.co/BAAI/bge-small-zh-v1.5/blob/main/README.md"
  }
}
```

### 诊断切片

切片 | 数量 | Hit@1 | Hit@3 | Hit@5 | MRR@5
--- | ---: | ---: | ---: | ---: | ---:
en | 13 | 0.0769 | 0.1538 | 0.4615 | 0.1756
zh | 8 | 0.1250 | 0.3750 | 0.3750 | 0.2500
cross_language | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000
same_language | 18 | 0.1111 | 0.2778 | 0.5000 | 0.2380
accelerator_design | 4 | 0.0000 | 0.0000 | 0.0000 | 0.0000
beam_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
beam_transport | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
control_architecture | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000
cryogenics | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
epics | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
interlock | 3 | 0.3333 | 1.0000 | 1.0000 | 0.6667
ioc | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
photon_diagnostics | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333
pv | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000
timing | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
epics-application-developers-guide-r3-16-2 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
epics-documentation-latest-2026-08-18 | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000
european-xfel-full-technical-design-report-2007 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
european-xfel-standard-e-beam-diagnostics-linac2010 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333
european-xfel-x-ray-optics-beam-transport-tdr-2012 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
shine-accelerator-control-system-design-presentation | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
shine-accelerator-fast-interlock-2024 | 2 | 0.0000 | 1.0000 | 1.0000 | 0.5000
shine-accelerator-preliminary-design-report-2017 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
shine-control-system-status-icalepcs2019 | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2000
shine-cryogenic-control-system-2021 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
shine-epics-ioc-pv-information-management-pcapac2022 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
shine-white-rabbit-beam-synchronous-timing-ipac2022 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250

### BM25 互补性

```json
{
  "counts": {
    "both_hit": 8,
    "bm25_only": 7,
    "dense_only": 1,
    "both_miss": 5
  },
  "query_ids": {
    "both_hit": [
      "epics-reconnect",
      "undulator-tuning",
      "xfel-bpm-types",
      "interlock-latency",
      "interlock-platform",
      "cryo-integration",
      "timing-wrtd",
      "control-slow-interlock"
    ],
    "bm25_only": [
      "epics-pp",
      "epics-cli",
      "xfel-mirror-angle",
      "xfel-soft-mono",
      "timing-jitter",
      "shine-compressors",
      "shine-main-linac"
    ],
    "dense_only": [
      "shine-control-layers"
    ],
    "both_miss": [
      "xfel-rf",
      "xfel-normal-energy",
      "shine-ioc-management",
      "shine-ioc-startup",
      "cryo-interlock"
    ]
  }
}
```

### 负例分数（仅在本模型内解释）

组别 | 数量 | 最小值 | 中位数 | 最大值
--- | ---: | ---: | ---: | ---:
answerable | 21 | 0.5109 | 0.6647 | 0.7783
obvious | 3 | 0.4102 | 0.4653 | 0.5546
hard_domain | 8 | 0.5559 | 0.6074 | 0.6791

未设置拒答阈值。高分只表示相似性，领域负例仍会返回结果。

### 逐条跨语言查询

- `xfel-normal-energy`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3, shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9, shine-accelerator-preliminary-design-report-2017:835d88bff1075ce44fb81c9d77fc57a3e79f88ea59067e025a3f6d45dbc5944d, shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf, shine-accelerator-preliminary-design-report-2017:8c9eae11d9baa8eecf40e783c9f2b825d2aa96e87dc4818ee8839a74108b7076。
- `shine-ioc-startup`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996, shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9, shine-accelerator-control-system-design-presentation:e1c35529e291cca970425ed8236272f89c4baf39b52b11de0bb8516839d73add, shine-accelerator-control-system-design-presentation:fa8c0077ece6768d8abd8b26f38ba9ec4b42dda3962adec3f580e4a0d1e7150c, shine-accelerator-control-system-design-presentation:b5e774526ee5277e9678ca88bbb1535b016522ea7bd8318244965a80f4845140。
- `cryo-interlock`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe, shine-accelerator-preliminary-design-report-2017:e0ca574b494f83092f3ce6afede8491d2e46262ccb0c0be04e1409c5064b788c, shine-accelerator-preliminary-design-report-2017:564c4f599876573d43395476bfeffe0b3284efc55de30f03de19658b625d33c0, shine-accelerator-preliminary-design-report-2017:16d7e5ceb43b87c870171a91ad97c3159c81d11ca48f808412d053d66d87d707, shine-accelerator-preliminary-design-report-2017:01fff83f895ea2e86d37d222f3fdb0b5cfdd417954575b52c2b7d91f5f67abc6。

### 已知失败逐条诊断

#### xfel-rf

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`european-xfel-full-technical-design-report-2007:7e13f57b72ac322f75090022eb0585cd4b8431657cde96be98988995f7fec0f7`，第 35 页；score 0.6366；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:7e13f57b72ac322f75090022eb0585cd4b8431657cde96be98988995f7fec0f7:p:e7297da1035f5b5b1b161dd61c074dc9001df5b83b8ae8c879ee5695ebb96b84`；passage 本身匹配 evidence：False。
- Rank 2：`european-xfel-full-technical-design-report-2007:bb1d668369f1b1f466b854f6e42b1977575f704be26dd60e936cebb40a9197a4`，第 311 页；score 0.6341；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:bb1d668369f1b1f466b854f6e42b1977575f704be26dd60e936cebb40a9197a4:p:12ae2c6869df5bcc0237fd7ebf005154379de123b0b22d995ba5e788f08d13a1`；passage 本身匹配 evidence：False。
- Rank 3：`european-xfel-full-technical-design-report-2007:a88dfd6995e1c22c618cb80aba4c3000a56ce212f4909c0fd533835576412d72`，第 376 页；score 0.6302；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:a88dfd6995e1c22c618cb80aba4c3000a56ce212f4909c0fd533835576412d72:p:85aa55b2b021aa4252e21e41f84c919daf1a6cd331087737ba0c12313c4f2986`；passage 本身匹配 evidence：False。
- Rank 4：`european-xfel-full-technical-design-report-2007:77278d80873d3a70fbf38f7d2a1a95fc110dc92b9f11836edf3a27b1cf756fc4`，第 493 页；score 0.6290；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:77278d80873d3a70fbf38f7d2a1a95fc110dc92b9f11836edf3a27b1cf756fc4:p:51af80b9ef984715721a5a941ea4a1f0e2b211a7d2b7b93e1ae8fb0737a8b51c`；passage 本身匹配 evidence：False。
- Rank 5：`european-xfel-full-technical-design-report-2007:4114e2f80525b6f692a9d21f46860c5d223a309e9e0ab210c1c7dff398f457c9`，第 353 页；score 0.6243；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:4114e2f80525b6f692a9d21f46860c5d223a309e9e0ab210c1c7dff398f457c9:p:f8283a91cf2981ce84c20816022b2fde92e9ae6e3ade577f01457939dce16656`；passage 本身匹配 evidence：False。

#### xfel-normal-energy

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3`，第 61 页；score 0.6484；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3:p:9ae8565630c457ac7dcc0fb1696d7bf117d1c0e86905b8a5f9d5b798be31a2f4`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9`，第 188 页；score 0.6329；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9:p:5977df5a7de38f21c91eb8d8ad94e76e83c9bc83bdc643ac381ad218b73f6da5`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-preliminary-design-report-2017:835d88bff1075ce44fb81c9d77fc57a3e79f88ea59067e025a3f6d45dbc5944d`，第 322 页；score 0.6172；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:835d88bff1075ce44fb81c9d77fc57a3e79f88ea59067e025a3f6d45dbc5944d:p:08d172cbf0e87f76003860ff1ee56f59b6755c6428c863814a0934f4fe702a0a`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`，第 193 页；score 0.6105；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf:p:9454f426ec4e2bb9c21f37b8554300d2faadc136e9b66f147d03ec8481c94ae6`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-preliminary-design-report-2017:8c9eae11d9baa8eecf40e783c9f2b825d2aa96e87dc4818ee8839a74108b7076`，第 63 页；score 0.6093；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:8c9eae11d9baa8eecf40e783c9f2b825d2aa96e87dc4818ee8839a74108b7076:p:839a7881c43c2fcd1ac254ac190bc6dc6e97abd3484f89ffe558a6ec603f5051`；passage 本身匹配 evidence：False。

#### shine-ioc-management

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355`，第 2 页；score 0.6562；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355:p:8ec12a423c1c368a4c41e580fee977ae07b49d082c04c9e78e6520cadfc29c50`；passage 本身匹配 evidence：False。
- Rank 2：`shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981`，第 3 页；score 0.6439；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981:p:e0fde11dd5eb06e54da90c5f6ccbd0107b83f7756a6531a8f837e08788180677`；passage 本身匹配 evidence：False。
- Rank 3：`shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60`，第 1 页；score 0.6418；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60:p:e842a5239788af855f3583e27a53fb725ea9d91465dca02d898a4eea6a43d417`；passage 本身匹配 evidence：False。
- Rank 4：`epics-documentation-latest-2026-08-18:9613124816a8df6b38a639ce490da04452a906eee438d97f2620b28ac098370e`，第 449 页；score 0.6265；父 Chunk 匹配至少一组 evidence：False；获胜 passage `epics-documentation-latest-2026-08-18:9613124816a8df6b38a639ce490da04452a906eee438d97f2620b28ac098370e:p:022d4ab8cb7c38d6df56bdd4a07d91ea65d6891506b9dc406f4d67fb34007204`；passage 本身匹配 evidence：False。
- Rank 5：`shine-epics-ioc-pv-information-management-pcapac2022:45bb8f1fef5da6c1a19bd7d54b4377c837852f77016220b79404478d7cc8a0e5`，第 2 页；score 0.6192；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:45bb8f1fef5da6c1a19bd7d54b4377c837852f77016220b79404478d7cc8a0e5:p:265f88874e633f5ef3eda89c0c32c13bc9e5fbaa7f90334c578877b528eb8c32`；passage 本身匹配 evidence：False。

#### shine-ioc-startup

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996`，第 28 页；score 0.6667；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996:p:73caea0cd714a21ce382914ae78abac333a8fc35acd0f106d977f318b58e0902`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`，第 10 页；score 0.6213；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9:p:ce48a5ee772c9e6a051f3b2c589735ff043578e78beb66c44d41fcd9c98498d7`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-control-system-design-presentation:e1c35529e291cca970425ed8236272f89c4baf39b52b11de0bb8516839d73add`，第 26 页；score 0.5832；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:e1c35529e291cca970425ed8236272f89c4baf39b52b11de0bb8516839d73add:p:f1edaf24ac50b7001175f72ea9170174469a14511e0055595f914676e52e6fb4`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-control-system-design-presentation:fa8c0077ece6768d8abd8b26f38ba9ec4b42dda3962adec3f580e4a0d1e7150c`，第 11 页；score 0.5796；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:fa8c0077ece6768d8abd8b26f38ba9ec4b42dda3962adec3f580e4a0d1e7150c:p:48e087f434d658f6a2917cfb2624f43c4eabbb022155bf7f107666613d841d27`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-control-system-design-presentation:b5e774526ee5277e9678ca88bbb1535b016522ea7bd8318244965a80f4845140`，第 12 页；score 0.5793；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:b5e774526ee5277e9678ca88bbb1535b016522ea7bd8318244965a80f4845140:p:49473f0521931ad77ec6a488e7237bed927f959763f805d70e5146a8eb68e676`；passage 本身匹配 evidence：False。

#### cryo-interlock

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe`，第 277 页；score 0.5953；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe:p:cbfa8e11c435db878859f8f3ab65a45b27084447a8c6e1af2a35e6dea242af68`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-preliminary-design-report-2017:e0ca574b494f83092f3ce6afede8491d2e46262ccb0c0be04e1409c5064b788c`，第 274 页；score 0.5811；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:e0ca574b494f83092f3ce6afede8491d2e46262ccb0c0be04e1409c5064b788c:p:79a1d8d10ec66ad23fc4c6444d58c0ab1d631efd8d49ae2cf6b1de73a35c7b0e`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-preliminary-design-report-2017:564c4f599876573d43395476bfeffe0b3284efc55de30f03de19658b625d33c0`，第 144 页；score 0.5689；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:564c4f599876573d43395476bfeffe0b3284efc55de30f03de19658b625d33c0:p:f062e68c423a6e4ea39fbf36e0bc11dccdf1e35b166eedcaca849bb07bf0b8d1`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-preliminary-design-report-2017:16d7e5ceb43b87c870171a91ad97c3159c81d11ca48f808412d053d66d87d707`，第 129 页；score 0.5675；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:16d7e5ceb43b87c870171a91ad97c3159c81d11ca48f808412d053d66d87d707:p:ac3931f3a1e937eed56eb1c7306fbe7ac798803d5d80770e34ddec1df056600b`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-preliminary-design-report-2017:01fff83f895ea2e86d37d222f3fdb0b5cfdd417954575b52c2b7d91f5f67abc6`，第 266 页；score 0.5657；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:01fff83f895ea2e86d37d222f3fdb0b5cfdd417954575b52c2b7d91f5f67abc6:p:e1583b4bc5a1198db5b843dd8e51e0532f380872a888b77d835edf804e003d25`；passage 本身匹配 evidence：False。

#### shine-compressors

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf`，第 193 页；score 0.5109；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:8be003019d5fa5b88c879c1c747daba6790459100a7f38b513a906bf76cbacbf:p:9454f426ec4e2bb9c21f37b8554300d2faadc136e9b66f147d03ec8481c94ae6`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，第 6 页；score 0.5030；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520:p:edcd8d1634ae669358305ffcf85563607212d28d9b6f0613011b8ddf4bcc5caa`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-preliminary-design-report-2017:c3dd78611920f09598f129f0e4d5216575f790c1d9508f8e77d478270a26468c`，第 197 页；score 0.4973；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:c3dd78611920f09598f129f0e4d5216575f790c1d9508f8e77d478270a26468c:p:ae3ed61af6f7abb2ce9bd71a7be928e31d4d67d36afed481f488db903e94268d`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-preliminary-design-report-2017:ef82fee1b2a3a4f09021f091f2e05a247a0a60843f3f3473347aa61c6fc367a2`，第 215 页；score 0.4957；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:ef82fee1b2a3a4f09021f091f2e05a247a0a60843f3f3473347aa61c6fc367a2:p:00d5b4d31d9b9e21758401ac31a0cb8ab7d5ae0ea31f7f3ff15bb6ef107ae0ce`；passage 本身匹配 evidence：False。
- Rank 5：`european-xfel-x-ray-optics-beam-transport-tdr-2012:b09e5bf33ea8a6b05f2224d235be2319262432830f702d010fbd656d64924d2a`，第 45 页；score 0.4929；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-x-ray-optics-beam-transport-tdr-2012:b09e5bf33ea8a6b05f2224d235be2319262432830f702d010fbd656d64924d2a:p:7f8c597fb69884bcb2c715619aec48e863bd893128f217218de0597c76751728`；passage 本身匹配 evidence：False。

#### shine-main-linac

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-control-system-design-presentation:6ef921c2c3cc45659c9744acd2df45838e9cbf0bce28f92d2d2dd8fcf1d5cf26`，第 8 页；score 0.6647；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:6ef921c2c3cc45659c9744acd2df45838e9cbf0bce28f92d2d2dd8fcf1d5cf26:p:29cc11897d190d62ddbd629c2a9644cc07ed18c3e8fd3b8749e7a6b7996ce1e2`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，第 6 页；score 0.6633；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520:p:edcd8d1634ae669358305ffcf85563607212d28d9b6f0613011b8ddf4bcc5caa`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8`，第 5 页；score 0.6629；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8:p:4e1ded3fd790d8525ed2e97081b32545adad20137ae540caebf6cff6eab7cd5f`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-control-system-design-presentation:f7ab778c51869e4f0c3013020278027e9f046b4b61540c73a840b9990c7895b0`，第 14 页；score 0.6544；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:f7ab778c51869e4f0c3013020278027e9f046b4b61540c73a840b9990c7895b0:p:21954dfd3e097c550b80cb935b465f8237274eb5764237455fac8c9b745752a2`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-control-system-design-presentation:8c276dddd8678c65c6372c0bcad311c6c354251802d910bf71d17e404b017e06`，第 9 页；score 0.6435；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:8c276dddd8678c65c6372c0bcad311c6c354251802d910bf71d17e404b017e06:p:00082e1ba086f92df4731fa93511ce180af7830cc3094fd63351437c882b04ad`；passage 本身匹配 evidence：False。


## intfloat/multilingual-e5-base

### 身份和成本

```json
{
  "fingerprint": {
    "requested_model_name": "intfloat/multilingual-e5-base",
    "resolved_local_model_path": "/home/whloong/projects/accelerator-rag/tmp/stage-two-seven/models/intfloat--multilingual-e5-base",
    "local_snapshot_id": null,
    "snapshot_identity_source": "downloaded local directory; no inferred revision",
    "model_config_sha256": "9dab198f24c8c0879e481cf7822005d5ecbceedbacb390ffafa594e28d31bac4",
    "config_files": {
      "1_Pooling/config.json": "f586ab6c734af7b8d14d898bfa7faa886f23b46f86dd1730514309893af13d75",
      "config.json": "9dab198f24c8c0879e481cf7822005d5ecbceedbacb390ffafa594e28d31bac4",
      "modules.json": "c6e29747481e8b5dd2b58401966aeac910de39092f90cda9a704b1545f902b04",
      "sentence_bert_config.json": "948201d8329907aae938fa62f9ceeed53f5694dacc2b87b9f3b78b37ee986529",
      "special_tokens_map.json": "06e405a36dfe4b9604f484f6a1e619af1a7f7d09e34a8555eb0b77b66318067f",
      "tokenizer.json": "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626",
      "tokenizer_config.json": "efb5c0d09722e5fe59a462cd2a9976ee216d55b037597d997cd3fe833216da15"
    },
    "tokenizer_sha256": "798f7509a92c8e84840c5c860ea274ac7de2e3df22bac00d3a81f45333733968",
    "weights_files": {
      "model.safetensors": "a18a44fad1d0b46ded15928144138cff1135d5cc8233bdd90be5f18822de09a7"
    },
    "weights_manifest_sha256": "923e74dc0f652fc6c0fbcdb3a76305e78a13f96c4b7a776e35c821da84bc5b05",
    "max_seq_length": 512,
    "dimension": 768,
    "query_template": "query: {query}",
    "document_prefix": "passage: ",
    "local_model_bytes": 1134534380
  },
  "passage_statistics": {
    "algorithm": "dense-passages-v1",
    "contract": {
      "algorithm": "dense-passages-v1",
      "config": {
        "max_tokens": null,
        "guard_tokens": 16,
        "overlap_tokens": 32
      },
      "tokenizer": {
        "model": "intfloat/multilingual-e5-base",
        "max_seq_length": 512,
        "tokenizer_sha256": "798f7509a92c8e84840c5c860ea274ac7de2e3df22bac00d3a81f45333733968",
        "do_lower_case": false,
        "template": "document_title + \"\\n\" + passage.text",
        "document_prefix": "passage: "
      },
      "effective_max_tokens": 512
    },
    "contract_id": "dba19095d5a1360bcdd72e7fbceddf594a23c364cbd423ebe3049dbd2975a0fb",
    "model_max_seq_length": 512,
    "eligible_parent_chunks": 4532,
    "embedding_passages": 4746,
    "parents_with_1_passage": 4324,
    "parents_split": 208,
    "average_passages_per_parent": 1.0472197705207413,
    "passages_per_parent": {
      "count": 4532,
      "min": 1,
      "max": 3,
      "mean": 1.0472197705207413,
      "p10": 1.0,
      "p25": 1.0,
      "median": 1.0,
      "p75": 1.0,
      "p90": 1.0,
      "p95": 1.0
    },
    "passage_token_length": {
      "count": 4746,
      "min": 10,
      "max": 512,
      "mean": 254.342393594606,
      "p10": 120.0,
      "p25": 180.0,
      "median": 253.0,
      "p75": 309.75,
      "p90": 398.0,
      "p95": 473.0
    },
    "passages_exceeding_limit": 0,
    "all_passage_inputs_within_model_limit": true,
    "guard_policy": "Already-fitting parent inputs remain unchanged; split windows reserve guard_tokens in the complete title+body+specials template.",
    "by_document": {
      "epics-application-developers-guide-r3-16-2": {
        "parents": 847,
        "passages": 874
      },
      "epics-documentation-latest-2026-08-18": {
        "parents": 1071,
        "passages": 1075
      },
      "european-xfel-full-technical-design-report-2007": {
        "parents": 1730,
        "passages": 1736
      },
      "european-xfel-standard-e-beam-diagnostics-linac2010": {
        "parents": 13,
        "passages": 13
      },
      "european-xfel-undulator-commissioning-spectrometer-cdr-2011": {
        "parents": 41,
        "passages": 41
      },
      "european-xfel-x-ray-optics-beam-transport-tdr-2012": {
        "parents": 235,
        "passages": 235
      },
      "shine-accelerator-control-system-design-presentation": {
        "parents": 33,
        "passages": 33
      },
      "shine-accelerator-fast-interlock-2024": {
        "parents": 18,
        "passages": 25
      },
      "shine-accelerator-preliminary-design-report-2017": {
        "parents": 477,
        "passages": 647
      },
      "shine-control-system-status-icalepcs2019": {
        "parents": 15,
        "passages": 15
      },
      "shine-cryogenic-control-system-2021": {
        "parents": 22,
        "passages": 22
      },
      "shine-epics-ioc-pv-information-management-pcapac2022": {
        "parents": 13,
        "passages": 13
      },
      "shine-white-rabbit-beam-synchronous-timing-ipac2022": {
        "parents": 17,
        "passages": 17
      }
    }
  },
  "collection": "knowledge_stage27_intfloat__multilingual_e5_base",
  "qdrant_path": "tmp/stage-two-seven/intfloat--multilingual-e5-base/qdrant",
  "timing": {
    "model_load_seconds": 1.8063539439899614,
    "fingerprint_seconds": 1.1716574980091536,
    "passage_preparation_seconds": 3.4702836880023824,
    "embedding_seconds": 0,
    "qdrant_indexing_seconds": 0,
    "point_count": 4746,
    "embedded_passage_count": 0,
    "unique_parent_count": 4532,
    "evaluation_seconds": 2.003824252009508
  },
  "vectors_reused": true,
  "historical_control_embedding_seconds": null,
  "control_reuse_note": null,
  "first_build_timing": {
    "model_load_seconds": 1.814460344001418,
    "fingerprint_seconds": 1.1678193349944195,
    "passage_preparation_seconds": 3.5266398769890657,
    "embedding_seconds": 1344.9193349220732,
    "qdrant_indexing_seconds": 11.259757676001755,
    "embedded_passage_count": 4746,
    "point_count": 4746,
    "unique_parent_count": 4532,
    "evaluation_seconds": 2.3520582690107403
  },
  "encoding_contract_source": {
    "local_path": "/home/whloong/projects/accelerator-rag/tmp/stage-two-seven/models/intfloat--multilingual-e5-base/README.md",
    "sha256": "9d129cb0b912b55c7b5378f976a9c35ae4796c80466b659ad63930d8ca090fca",
    "publisher_url": "https://huggingface.co/intfloat/multilingual-e5-base/blob/main/README.md"
  },
  "download_provenance": {
    "source": "local huggingface_hub download metadata file",
    "path": "/home/whloong/projects/accelerator-rag/tmp/stage-two-seven/models/intfloat--multilingual-e5-base/.cache/huggingface/download/config.json.metadata",
    "downloaded_commit": "d128750597153bb5987e10b1c3493a34e5a4502a"
  }
}
```

### 诊断切片

切片 | 数量 | Hit@1 | Hit@3 | Hit@5 | MRR@5
--- | ---: | ---: | ---: | ---: | ---:
en | 13 | 0.3846 | 0.7692 | 0.9231 | 0.6115
zh | 8 | 0.1250 | 0.3750 | 0.5000 | 0.2604
cross_language | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000
same_language | 18 | 0.3333 | 0.7222 | 0.8889 | 0.5574
accelerator_design | 4 | 0.0000 | 0.0000 | 0.5000 | 0.1125
beam_diagnostics | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000
beam_transport | 2 | 0.5000 | 1.0000 | 1.0000 | 0.7500
control_architecture | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2500
cryogenics | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000
epics | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000
interlock | 3 | 0.3333 | 1.0000 | 1.0000 | 0.6111
ioc | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
photon_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
pv | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000
timing | 2 | 0.0000 | 1.0000 | 1.0000 | 0.5000
epics-application-developers-guide-r3-16-2 | 2 | 1.0000 | 1.0000 | 1.0000 | 1.0000
epics-documentation-latest-2026-08-18 | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000
european-xfel-full-technical-design-report-2007 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1000
european-xfel-standard-e-beam-diagnostics-linac2010 | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000
european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
european-xfel-x-ray-optics-beam-transport-tdr-2012 | 2 | 0.5000 | 1.0000 | 1.0000 | 0.7500
shine-accelerator-control-system-design-presentation | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
shine-accelerator-fast-interlock-2024 | 2 | 0.0000 | 1.0000 | 1.0000 | 0.4167
shine-accelerator-preliminary-design-report-2017 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
shine-control-system-status-icalepcs2019 | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2500
shine-cryogenic-control-system-2021 | 2 | 0.5000 | 0.5000 | 0.5000 | 0.5000
shine-epics-ioc-pv-information-management-pcapac2022 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
shine-white-rabbit-beam-synchronous-timing-ipac2022 | 2 | 0.0000 | 1.0000 | 1.0000 | 0.5000

### BM25 互补性

```json
{
  "counts": {
    "both_hit": 14,
    "bm25_only": 1,
    "dense_only": 2,
    "both_miss": 4
  },
  "query_ids": {
    "both_hit": [
      "epics-pp",
      "epics-reconnect",
      "epics-cli",
      "undulator-tuning",
      "xfel-mirror-angle",
      "xfel-soft-mono",
      "xfel-bpm-types",
      "interlock-latency",
      "interlock-platform",
      "cryo-integration",
      "timing-wrtd",
      "timing-jitter",
      "control-slow-interlock",
      "shine-compressors"
    ],
    "bm25_only": [
      "shine-main-linac"
    ],
    "dense_only": [
      "xfel-rf",
      "shine-control-layers"
    ],
    "both_miss": [
      "xfel-normal-energy",
      "shine-ioc-management",
      "shine-ioc-startup",
      "cryo-interlock"
    ]
  }
}
```

### 负例分数（仅在本模型内解释）

组别 | 数量 | 最小值 | 中位数 | 最大值
--- | ---: | ---: | ---: | ---:
answerable | 21 | 0.8583 | 0.8821 | 0.9243
obvious | 3 | 0.7803 | 0.8031 | 0.8310
hard_domain | 8 | 0.8103 | 0.8514 | 0.8826

未设置拒答阈值。高分只表示相似性，领域负例仍会返回结果。

### 逐条跨语言查询

- `xfel-normal-energy`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-preliminary-design-report-2017:5b41bd7b2775af04f235849ab045b68eec206ed441535409dc83bb395c1937f9, shine-accelerator-preliminary-design-report-2017:236a227e1101bfab2e32bdc135b766a9c399c3ad8332d18038ab99ffad8b0418, shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9, shine-accelerator-preliminary-design-report-2017:505c103217db05090bc6af4957bea3a0f25408c839e892ecf43434e19a818855, shine-accelerator-preliminary-design-report-2017:f291845a245b36af7a4e324f76e5b4332fe242cb9b7dfed7edde83bc289cc454。
- `shine-ioc-startup`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996, shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9, shine-accelerator-control-system-design-presentation:c974bab1b4639369581c694e815a965edb4c260986cad2d5d5a0210c6e1b2229, shine-accelerator-control-system-design-presentation:cc861f21498d70716841017740bb172e073392ca6cffb5cf0fabff4509daaf45, shine-accelerator-preliminary-design-report-2017:d1615c0ba7dd7e6e2c2c69b2400e44031b50b3c1a645a5ea738c82964825aed1。
- `cryo-interlock`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b, shine-accelerator-fast-interlock-2024:aae02c59d825aff4aeea7aba93cbe89b3f572cde5688850c012d93e8a027a748, shine-accelerator-fast-interlock-2024:ae04095dfd876f0d7d347ee1e1e867b2fec36c6bffbb5c118731167fefa2b129, shine-accelerator-control-system-design-presentation:09458ab097d77634fa3f168e23bc0e98db5fa58eb691d500f65d4f61a5dd94fc, shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a。

### 已知失败逐条诊断

#### xfel-rf

完整父 Chunk 证据首次排名：5；仅按获胜 passage 判断的完整证据首次排名：5。

- Rank 1：`european-xfel-full-technical-design-report-2007:a54585a77a3e23563e22dd291db142fff5d0bbc8fd88d2a74a00c32a31148216`，第 98 页；score 0.8656；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:a54585a77a3e23563e22dd291db142fff5d0bbc8fd88d2a74a00c32a31148216:p:b77e020c49d4fec8f4e00209f938d878e520a51d226fbabe9c895d639f8fcaa8`；passage 本身匹配 evidence：False。
- Rank 2：`european-xfel-full-technical-design-report-2007:66fe8f7d369d58380b218e11f28e1a1c7b82b7b4dc63112857884404967fed2a`，第 57 页；score 0.8645；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:66fe8f7d369d58380b218e11f28e1a1c7b82b7b4dc63112857884404967fed2a:p:fa30731e119c038ba93e40d7776dabc68509b721443b9116bff59c3f71035e01`；passage 本身匹配 evidence：False。
- Rank 3：`european-xfel-full-technical-design-report-2007:c50ce3cf699068e23e08a7c362fc0c26e977023f790b2f20d51a982e90572b1a`，第 71 页；score 0.8643；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:c50ce3cf699068e23e08a7c362fc0c26e977023f790b2f20d51a982e90572b1a:p:b1c81eb0ca4a9967d4649bbe7b46d299a3d4b1703a026353431947a8a6becb14`；passage 本身匹配 evidence：False。
- Rank 4：`european-xfel-full-technical-design-report-2007:8c0bf12b5e28e34675144bbe6d05e3a2389bfbb7bb19ee854045286591925d03`，第 116 页；score 0.8615；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:8c0bf12b5e28e34675144bbe6d05e3a2389bfbb7bb19ee854045286591925d03:p:f54a8d2f4a8100bdfd0f0964c0c555db6e963f016b60c17db6fc2515627ff0cd`；passage 本身匹配 evidence：False。
- Rank 5：`european-xfel-full-technical-design-report-2007:a28479a4c17014782d0ce4480528110f45f1eb55e9ec9367c7e80787abb2f78d`，第 65 页；score 0.8587；父 Chunk 匹配至少一组 evidence：True；获胜 passage `european-xfel-full-technical-design-report-2007:a28479a4c17014782d0ce4480528110f45f1eb55e9ec9367c7e80787abb2f78d:p:da069c53c518cc33c30512e024d9edd880c29aaa46bda0d868a4496c0ac40d4e`；passage 本身匹配 evidence：True。

#### xfel-normal-energy

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-preliminary-design-report-2017:5b41bd7b2775af04f235849ab045b68eec206ed441535409dc83bb395c1937f9`，第 59 页；score 0.8796；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:5b41bd7b2775af04f235849ab045b68eec206ed441535409dc83bb395c1937f9:p:ffb90ead66d07c0a6dc61b66c73c7fa52f0db8af4a279da46c743ee67223071f`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-preliminary-design-report-2017:236a227e1101bfab2e32bdc135b766a9c399c3ad8332d18038ab99ffad8b0418`，第 83 页；score 0.8785；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:236a227e1101bfab2e32bdc135b766a9c399c3ad8332d18038ab99ffad8b0418:p:a3222e9c479f06b4f329d888a8509fccf5f7a91ff57561d7f8d6612ab622a199`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9`，第 188 页；score 0.8764；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:015b678ae3eeb30da6f3b8e67ff8a8c678589c9b3cdda22a13400caa5f6b67e9:p:bb3ddda5c1bb895319d85da2277566c057b4f01a0dde23820617a5b0ad763544`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-preliminary-design-report-2017:505c103217db05090bc6af4957bea3a0f25408c839e892ecf43434e19a818855`，第 65 页；score 0.8760；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:505c103217db05090bc6af4957bea3a0f25408c839e892ecf43434e19a818855:p:d4dbcd2829b7103b5113587623d28356f19595a7ab0c96e23200d195ecfad060`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-preliminary-design-report-2017:f291845a245b36af7a4e324f76e5b4332fe242cb9b7dfed7edde83bc289cc454`，第 185 页；score 0.8750；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:f291845a245b36af7a4e324f76e5b4332fe242cb9b7dfed7edde83bc289cc454:p:508f004df4a2d43d79264c793741a473f1eb8a2ced91a765372a6c4157da1dd1`；passage 本身匹配 evidence：False。

#### shine-ioc-management

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355`，第 2 页；score 0.9011；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355:p:110c1390b56234f0f0b168d1605fd43d8666fe33fa6287e9446c4e2040596540`；passage 本身匹配 evidence：False。
- Rank 2：`shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60`，第 1 页；score 0.8934；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:ee367f0a36287d1f95b22845d0f2103fb4b0cd22ef4421024730762fe0ed6d60:p:aec023a5baec5017b0383fe9f0ea433be12e3a3860cda6e9c85bc3399dbeb166`；passage 本身匹配 evidence：False。
- Rank 3：`shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981`，第 3 页；score 0.8894；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981:p:0b304060a86c29b675eee433ac56d6b6b41729c66c0e02d4fb18b91e3540f705`；passage 本身匹配 evidence：False。
- Rank 4：`shine-epics-ioc-pv-information-management-pcapac2022:6b532252b1d9b5d12ff2e3846095924490c1864b4f7f864b57d511bf95da5bd2`，第 1 页；score 0.8892；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:6b532252b1d9b5d12ff2e3846095924490c1864b4f7f864b57d511bf95da5bd2:p:113eb108e39647763198c60b43c8fb5290af5804c5201c0c61283b8553452ac1`；passage 本身匹配 evidence：True。
- Rank 5：`shine-epics-ioc-pv-information-management-pcapac2022:45bb8f1fef5da6c1a19bd7d54b4377c837852f77016220b79404478d7cc8a0e5`，第 2 页；score 0.8889；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:45bb8f1fef5da6c1a19bd7d54b4377c837852f77016220b79404478d7cc8a0e5:p:c50d9fa807747a3f6ad670077a92937242f97633f2b47dc4a30faf8b1db11350`；passage 本身匹配 evidence：False。

#### shine-ioc-startup

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996`，第 28 页；score 0.8869；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996:p:0646a34307f529bc7de02f7d93761e174d98857c7eaf5fccc6460588aaba27b3`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`，第 10 页；score 0.8839；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9:p:2366c9ab442c1dad6570a9455ba4abc8f9af56d9b6eb61325286af8f2da12666`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-control-system-design-presentation:c974bab1b4639369581c694e815a965edb4c260986cad2d5d5a0210c6e1b2229`，第 19 页；score 0.8747；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:c974bab1b4639369581c694e815a965edb4c260986cad2d5d5a0210c6e1b2229:p:319456297a53065e801a6362775d9eee028219078ed10442d1f32c0c61e89c36`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-control-system-design-presentation:cc861f21498d70716841017740bb172e073392ca6cffb5cf0fabff4509daaf45`，第 29 页；score 0.8723；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:cc861f21498d70716841017740bb172e073392ca6cffb5cf0fabff4509daaf45:p:5ffc9e4eea8d8c2d90771b48173f7b8e172c3c31b588f2aa2f0e9689b2a4c488`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-preliminary-design-report-2017:d1615c0ba7dd7e6e2c2c69b2400e44031b50b3c1a645a5ea738c82964825aed1`，第 387 页；score 0.8720；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:d1615c0ba7dd7e6e2c2c69b2400e44031b50b3c1a645a5ea738c82964825aed1:p:3eca039b8eade6423314058e19c20c5f5f9541d20f3daea3fccaab0f216aa762`；passage 本身匹配 evidence：False。

#### cryo-interlock

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`，第 2 页；score 0.8933；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b:p:3088e5456f3ffdc72576b3f7579cddcbf20d5b4718de4b098b1a6eebd7b6e186`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-fast-interlock-2024:aae02c59d825aff4aeea7aba93cbe89b3f572cde5688850c012d93e8a027a748`，第 4 页；score 0.8880；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:aae02c59d825aff4aeea7aba93cbe89b3f572cde5688850c012d93e8a027a748:p:7f6d47b52192f46e08985bbcb1f13e319e6fd036a90c745b82432801d3c74e1b`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-fast-interlock-2024:ae04095dfd876f0d7d347ee1e1e867b2fec36c6bffbb5c118731167fefa2b129`，第 9 页；score 0.8838；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:ae04095dfd876f0d7d347ee1e1e867b2fec36c6bffbb5c118731167fefa2b129:p:c2c8367b2749f218b10d97da24216ed75ce545ab497fab46fc3951acc17eccaa`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-control-system-design-presentation:09458ab097d77634fa3f168e23bc0e98db5fa58eb691d500f65d4f61a5dd94fc`，第 22 页；score 0.8825；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:09458ab097d77634fa3f168e23bc0e98db5fa58eb691d500f65d4f61a5dd94fc:p:0a0f119107539ebae223b9a0f19b33f27d78229ca280199743da917d6e2aa3bf`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a`，第 3 页；score 0.8825；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:a5b7baa31dd6b7e2bccef2a847deb913b96aac8381844a10f7aa0d1ea5b4ac6a:p:d12acd1f3f575ef8f12df6b6c3fbee36520e62a767be10ce2bb11e137bef35b8`；passage 本身匹配 evidence：False。

#### shine-compressors

完整父 Chunk 证据首次排名：4；仅按获胜 passage 判断的完整证据首次排名：4。

- Rank 1：`shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`，第 2 页；score 0.8773；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b:p:3088e5456f3ffdc72576b3f7579cddcbf20d5b4718de4b098b1a6eebd7b6e186`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-fast-interlock-2024:ca6ed3ab0a05a8078e2b676d8505143428716244a402efe44febb2045d2de736`，第 1 页；score 0.8766；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:ca6ed3ab0a05a8078e2b676d8505143428716244a402efe44febb2045d2de736:p:3387f1166cc19d7c21aa26fc13a2e610527281b369800fb6d057ad485df57838`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，第 6 页；score 0.8735；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520:p:07c388c8bbfc8db660b7eeabe73b4907a5a08b49cfad0fe5d998f015097e63e7`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3`，第 61 页；score 0.8715；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3:p:437af49daa892d4345ecea862ad2e69e3ef69e1c9cd578643609b75313f711b8`；passage 本身匹配 evidence：True。
- Rank 5：`shine-accelerator-fast-interlock-2024:aae02c59d825aff4aeea7aba93cbe89b3f572cde5688850c012d93e8a027a748`，第 4 页；score 0.8686；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:aae02c59d825aff4aeea7aba93cbe89b3f572cde5688850c012d93e8a027a748:p:aa69b12a6d4e0805897493e6c7b578e6fc551ba0a7c20e1ae95b73ac99ead3fa`；passage 本身匹配 evidence：False。

#### shine-main-linac

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-preliminary-design-report-2017:cf8f273a1807979a26bbeb8f961f70b0886235053ba0f7b80ee3989f17712b7b`，第 60 页；score 0.8839；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:cf8f273a1807979a26bbeb8f961f70b0886235053ba0f7b80ee3989f17712b7b:p:3b3353887733bc4674556b819ce6e7c1b8f15a949f307e586260f6904bf3f47b`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-control-system-design-presentation:eb2e90b2ac3aeb540f8b3995ad4be3262cefb8384e5e4085cb23e230dbf2308a`，第 5 页；score 0.8799；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:eb2e90b2ac3aeb540f8b3995ad4be3262cefb8384e5e4085cb23e230dbf2308a:p:b9a8c6d2adf4ebc66cb8e09ae1d6db28c64232972f4c35df97b5dcde81771ab6`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8`，第 5 页；score 0.8794；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8:p:ea979e50098d4cf3d494bc72d0b5281d459503d363a1ac12c86d1a5d6f4d14bd`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，第 6 页；score 0.8788；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520:p:07c388c8bbfc8db660b7eeabe73b4907a5a08b49cfad0fe5d998f015097e63e7`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-fast-interlock-2024:508e70c7e7387d951a35f023453d08ca74510b203abf6484060010eea25c6779`，第 6 页；score 0.8785；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:508e70c7e7387d951a35f023453d08ca74510b203abf6484060010eea25c6779:p:ff399d1e5174f02819da2bc597a29450d813f171380261f342919ae77febd3a6`；passage 本身匹配 evidence：False。


## BAAI/bge-base-zh-v1.5

### 身份和成本

```json
{
  "fingerprint": {
    "requested_model_name": "BAAI/bge-base-zh-v1.5",
    "resolved_local_model_path": "/home/whloong/projects/accelerator-rag/tmp/stage-two-seven/models/BAAI--bge-base-zh-v1.5",
    "local_snapshot_id": null,
    "snapshot_identity_source": "downloaded local directory; no inferred revision",
    "model_config_sha256": "6675c035d945dffc89f77a04a254b87cc193a9185a098bb505fe4963b6ddbac1",
    "config_files": {
      "1_Pooling/config.json": "c9bef85e8bbf4b2eab4941b3fb62bd33f88686748b478f2e264d256472d9643b",
      "config.json": "6675c035d945dffc89f77a04a254b87cc193a9185a098bb505fe4963b6ddbac1",
      "config_sentence_transformers.json": "940d5f50db195fa6e5e6a4f122c095f77880de259d74b14a65779ed48bdd7c56",
      "modules.json": "84e40c8e006c9b1d6c122e02cba9b02458120b5fb0c87b746c41e0207cf642cf",
      "sentence_bert_config.json": "84e39fda68ccbff05bfa723ae9c0e70e23e2ec373b76e0f8c6e71af72a693cbf",
      "special_tokens_map.json": "b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3",
      "tokenizer.json": "7dfbf1966ebf99d471c3796e9b457329d2b2182b817e144f1e904b957745c839",
      "tokenizer_config.json": "9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3"
    },
    "tokenizer_sha256": "eccb0da01ac8eb27055fffe5d9526e2dd137a5a3ae9d195a042bc47b9a59d378",
    "weights_files": {
      "pytorch_model.bin": "731cf5d88ed555a21ff2f2d9fa4db43b10489173ddd9178db3eecfd7a2bae044"
    },
    "weights_manifest_sha256": "41120841ab1c6f8fe528565bbde63b90fbcd318cdac12cd9cab237462de7e438",
    "max_seq_length": 512,
    "dimension": 768,
    "query_template": "为这个句子生成表示以用于检索相关文章：{query}",
    "document_prefix": "",
    "local_model_bytes": 409717615
  },
  "passage_statistics": {
    "algorithm": "dense-passages-v1",
    "contract": {
      "algorithm": "dense-passages-v1",
      "config": {
        "max_tokens": null,
        "guard_tokens": 16,
        "overlap_tokens": 32
      },
      "tokenizer": {
        "model": "BAAI/bge-base-zh-v1.5",
        "max_seq_length": 512,
        "tokenizer_sha256": "eccb0da01ac8eb27055fffe5d9526e2dd137a5a3ae9d195a042bc47b9a59d378",
        "do_lower_case": true,
        "template": "document_title + \"\\n\" + passage.text"
      },
      "effective_max_tokens": 512
    },
    "contract_id": "3b087ddb9df90cf754089327d0e381f3eb137609227e46c411bb7ca126609f67",
    "model_max_seq_length": 512,
    "eligible_parent_chunks": 4532,
    "embedding_passages": 4952,
    "parents_with_1_passage": 4154,
    "parents_split": 378,
    "average_passages_per_parent": 1.0926743159752867,
    "passages_per_parent": {
      "count": 4532,
      "min": 1,
      "max": 4,
      "mean": 1.0926743159752867,
      "p10": 1.0,
      "p25": 1.0,
      "median": 1.0,
      "p75": 1.0,
      "p90": 1.0,
      "p95": 2.0
    },
    "passage_token_length": {
      "count": 4952,
      "min": 8,
      "max": 512,
      "mean": 315.51696284329563,
      "p10": 149.0,
      "p25": 231.75,
      "median": 334.0,
      "p75": 399.0,
      "p90": 463.0,
      "p95": 483.0
    },
    "passages_exceeding_limit": 0,
    "all_passage_inputs_within_model_limit": true,
    "guard_policy": "Already-fitting parent inputs remain unchanged; split windows reserve guard_tokens in the complete title+body+specials template.",
    "by_document": {
      "epics-application-developers-guide-r3-16-2": {
        "parents": 847,
        "passages": 858
      },
      "epics-documentation-latest-2026-08-18": {
        "parents": 1071,
        "passages": 1086
      },
      "european-xfel-full-technical-design-report-2007": {
        "parents": 1730,
        "passages": 1782
      },
      "european-xfel-standard-e-beam-diagnostics-linac2010": {
        "parents": 13,
        "passages": 13
      },
      "european-xfel-undulator-commissioning-spectrometer-cdr-2011": {
        "parents": 41,
        "passages": 41
      },
      "european-xfel-x-ray-optics-beam-transport-tdr-2012": {
        "parents": 235,
        "passages": 246
      },
      "shine-accelerator-control-system-design-presentation": {
        "parents": 33,
        "passages": 33
      },
      "shine-accelerator-fast-interlock-2024": {
        "parents": 18,
        "passages": 27
      },
      "shine-accelerator-preliminary-design-report-2017": {
        "parents": 477,
        "passages": 799
      },
      "shine-control-system-status-icalepcs2019": {
        "parents": 15,
        "passages": 15
      },
      "shine-cryogenic-control-system-2021": {
        "parents": 22,
        "passages": 22
      },
      "shine-epics-ioc-pv-information-management-pcapac2022": {
        "parents": 13,
        "passages": 13
      },
      "shine-white-rabbit-beam-synchronous-timing-ipac2022": {
        "parents": 17,
        "passages": 17
      }
    }
  },
  "collection": "knowledge_stage27_baai__bge_base_zh_v1.5",
  "qdrant_path": "tmp/stage-two-seven/baai--bge-base-zh-v1.5/qdrant",
  "timing": {
    "model_load_seconds": 0.073061178001808,
    "fingerprint_seconds": 0.29462050199799705,
    "passage_preparation_seconds": 3.722785625999677,
    "embedding_seconds": 0,
    "qdrant_indexing_seconds": 0,
    "point_count": 4952,
    "embedded_passage_count": 0,
    "unique_parent_count": 4532,
    "evaluation_seconds": 2.6613159850094235
  },
  "vectors_reused": true,
  "historical_control_embedding_seconds": null,
  "control_reuse_note": null,
  "first_build_timing": {
    "model_load_seconds": 0.077270049994695,
    "fingerprint_seconds": 0.3418700610054657,
    "passage_preparation_seconds": 4.107497775999946,
    "embedding_seconds": 1433.4161751799402,
    "qdrant_indexing_seconds": 11.663046590037993,
    "embedded_passage_count": 4952,
    "point_count": 4952,
    "unique_parent_count": 4532,
    "evaluation_seconds": 2.9587889190006536
  },
  "encoding_contract_source": {
    "local_path": "/home/whloong/projects/accelerator-rag/tmp/stage-two-seven/models/BAAI--bge-base-zh-v1.5/README.md",
    "sha256": "7f8d638125f442bc2409edf5958dbce3086d91133e79831eff760c6ea2398740",
    "publisher_url": "https://huggingface.co/BAAI/bge-base-zh-v1.5/blob/main/README.md"
  },
  "download_provenance": {
    "source": "local huggingface_hub download metadata file",
    "path": "/home/whloong/projects/accelerator-rag/tmp/stage-two-seven/models/BAAI--bge-base-zh-v1.5/.cache/huggingface/download/config.json.metadata",
    "downloaded_commit": "f03589ceff5aac7111bd60cfc7d497ca17ecac65"
  }
}
```

### 诊断切片

切片 | 数量 | Hit@1 | Hit@3 | Hit@5 | MRR@5
--- | ---: | ---: | ---: | ---: | ---:
en | 13 | 0.1538 | 0.3846 | 0.6923 | 0.3295
zh | 8 | 0.0000 | 0.5000 | 0.5000 | 0.1875
cross_language | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000
same_language | 18 | 0.1111 | 0.5000 | 0.7222 | 0.3213
accelerator_design | 4 | 0.0000 | 0.2500 | 0.2500 | 0.0833
beam_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
beam_transport | 2 | 0.0000 | 0.5000 | 0.5000 | 0.2500
control_architecture | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2500
cryogenics | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
epics | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1000
interlock | 3 | 0.0000 | 1.0000 | 1.0000 | 0.3889
ioc | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
photon_diagnostics | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
pv | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000
timing | 2 | 0.0000 | 0.5000 | 0.5000 | 0.1667
epics-application-developers-guide-r3-16-2 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1000
epics-documentation-latest-2026-08-18 | 1 | 0.0000 | 1.0000 | 1.0000 | 0.5000
european-xfel-full-technical-design-report-2007 | 2 | 0.0000 | 0.0000 | 0.0000 | 0.0000
european-xfel-standard-e-beam-diagnostics-linac2010 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 1 | 1.0000 | 1.0000 | 1.0000 | 1.0000
european-xfel-x-ray-optics-beam-transport-tdr-2012 | 2 | 0.0000 | 0.5000 | 0.5000 | 0.2500
shine-accelerator-control-system-design-presentation | 1 | 0.0000 | 1.0000 | 1.0000 | 0.3333
shine-accelerator-fast-interlock-2024 | 2 | 0.0000 | 1.0000 | 1.0000 | 0.4167
shine-accelerator-preliminary-design-report-2017 | 2 | 0.0000 | 0.5000 | 0.5000 | 0.1667
shine-control-system-status-icalepcs2019 | 1 | 0.0000 | 0.0000 | 1.0000 | 0.2500
shine-cryogenic-control-system-2021 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
shine-epics-ioc-pv-information-management-pcapac2022 | 2 | 0.0000 | 0.0000 | 0.5000 | 0.1250
shine-white-rabbit-beam-synchronous-timing-ipac2022 | 2 | 0.0000 | 0.5000 | 0.5000 | 0.1667

### BM25 互补性

```json
{
  "counts": {
    "both_hit": 11,
    "bm25_only": 4,
    "dense_only": 2,
    "both_miss": 4
  },
  "query_ids": {
    "both_hit": [
      "epics-pp",
      "epics-cli",
      "undulator-tuning",
      "xfel-mirror-angle",
      "xfel-bpm-types",
      "interlock-latency",
      "interlock-platform",
      "cryo-integration",
      "timing-wrtd",
      "control-slow-interlock",
      "shine-compressors"
    ],
    "bm25_only": [
      "epics-reconnect",
      "xfel-soft-mono",
      "timing-jitter",
      "shine-main-linac"
    ],
    "dense_only": [
      "shine-ioc-management",
      "shine-control-layers"
    ],
    "both_miss": [
      "xfel-rf",
      "xfel-normal-energy",
      "shine-ioc-startup",
      "cryo-interlock"
    ]
  }
}
```

### 负例分数（仅在本模型内解释）

组别 | 数量 | 最小值 | 中位数 | 最大值
--- | ---: | ---: | ---: | ---:
answerable | 21 | 0.4713 | 0.5935 | 0.6908
obvious | 3 | 0.2832 | 0.3967 | 0.4237
hard_domain | 8 | 0.4381 | 0.5089 | 0.5414

未设置拒答阈值。高分只表示相似性，领域负例仍会返回结果。

### 逐条跨语言查询

- `xfel-normal-energy`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：european-xfel-full-technical-design-report-2007:77278d80873d3a70fbf38f7d2a1a95fc110dc92b9f11836edf3a27b1cf756fc4, european-xfel-full-technical-design-report-2007:994b41079e7544990a3cd70f346b1a3708f4361af77c83f2894a656e5eddb12e, european-xfel-full-technical-design-report-2007:f97acc766064b7555814cf3cb3722a86e8aab53d6db0d496af949586344c0685, european-xfel-full-technical-design-report-2007:32b43251188eed1c6604d6a4dcf69c4b05950b12f3664701713fb091ee714e5c, european-xfel-full-technical-design-report-2007:4fcb555cc63e04dbb22a81728ae9d0803ed38a23f083a36ee309806f48e8aaed。
- `shine-ioc-startup`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996, shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9, shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355, shine-epics-ioc-pv-information-management-pcapac2022:dbbe5b3ca2a4ae4ff7f7debebe9fc61aa28441bfff953e06bf43c18deaa03696, shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981。
- `cryo-interlock`：查询语言 zh；目标文档语言 ['en']；完整证据首次排名 None；Top-5：shine-cryogenic-control-system-2021:ddacec98352d4a3364b0ed059ee45daccd318912026ba96e0e2849bf8bc6de8d, shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe, shine-accelerator-preliminary-design-report-2017:90978b5dd35c9a8198a73fbe358f5215d18644ad865b44c89d5f9cdc7baed421, shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120, shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b。

### 已知失败逐条诊断

#### xfel-rf

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`european-xfel-full-technical-design-report-2007:f92a6743f6904563a002ff5bada8cca0cedee19894952f533bd7e4cfb1442f68`，第 84 页；score 0.6283；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:f92a6743f6904563a002ff5bada8cca0cedee19894952f533bd7e4cfb1442f68:p:01ca8e675d7f0a43bc0cac57b0b03d77a5eea83b7e4480b1ebcc875c81da615a`；passage 本身匹配 evidence：False。
- Rank 2：`european-xfel-full-technical-design-report-2007:e2a6e1b4cb3222dea424c0349fee641b25a6dc7ccaa63a44ef8aa23287bda137`，第 175 页；score 0.6128；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:e2a6e1b4cb3222dea424c0349fee641b25a6dc7ccaa63a44ef8aa23287bda137:p:8a89d7f6c9b87d93a396b5f495c354a3046799ee3406088c5e8179792c3c32ad`；passage 本身匹配 evidence：False。
- Rank 3：`european-xfel-full-technical-design-report-2007:01d2db89d25fb3673d497dd352c9db562458f48f82573984632015ee29554783`，第 67 页；score 0.6077；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:01d2db89d25fb3673d497dd352c9db562458f48f82573984632015ee29554783:p:36c2f2266c11a34ceb4498b1a2f41cc6a99a5eefa1e17b901180d1601b5ca0e4`；passage 本身匹配 evidence：False。
- Rank 4：`european-xfel-full-technical-design-report-2007:3a284af04dcd5e8188c4fdfb24c246c2fc7020d6a5d34d20e7c0025e174ffb33`，第 98 页；score 0.5958；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:3a284af04dcd5e8188c4fdfb24c246c2fc7020d6a5d34d20e7c0025e174ffb33:p:052fde94ad1b0b5e25d78e4806d099b2614662127d2ade0469d72dbef9fcdc6e`；passage 本身匹配 evidence：False。
- Rank 5：`european-xfel-full-technical-design-report-2007:a54585a77a3e23563e22dd291db142fff5d0bbc8fd88d2a74a00c32a31148216`，第 98 页；score 0.5957；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:a54585a77a3e23563e22dd291db142fff5d0bbc8fd88d2a74a00c32a31148216:p:bcb12331ae48395d8015f67b916619c5af3599dbfd093af431cad1cc451d36fe`；passage 本身匹配 evidence：False。

#### xfel-normal-energy

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`european-xfel-full-technical-design-report-2007:77278d80873d3a70fbf38f7d2a1a95fc110dc92b9f11836edf3a27b1cf756fc4`，第 493 页；score 0.5474；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:77278d80873d3a70fbf38f7d2a1a95fc110dc92b9f11836edf3a27b1cf756fc4:p:011ccb163dab2fdbdb4192db17f6c32d4d580db146a13afcaf26b6901ab3d769`；passage 本身匹配 evidence：False。
- Rank 2：`european-xfel-full-technical-design-report-2007:994b41079e7544990a3cd70f346b1a3708f4361af77c83f2894a656e5eddb12e`，第 191 页；score 0.5448；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:994b41079e7544990a3cd70f346b1a3708f4361af77c83f2894a656e5eddb12e:p:f540b69b5bc8090f6ce4ee748d29af04d66ce334fca9f940eb61697ef5049a31`；passage 本身匹配 evidence：False。
- Rank 3：`european-xfel-full-technical-design-report-2007:f97acc766064b7555814cf3cb3722a86e8aab53d6db0d496af949586344c0685`，第 195 页；score 0.5398；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:f97acc766064b7555814cf3cb3722a86e8aab53d6db0d496af949586344c0685:p:11df214afa9538e6f5979fa605602c7f38c3a33d4ae5006cc55fdbf884c69f82`；passage 本身匹配 evidence：False。
- Rank 4：`european-xfel-full-technical-design-report-2007:32b43251188eed1c6604d6a4dcf69c4b05950b12f3664701713fb091ee714e5c`，第 99 页；score 0.5326；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:32b43251188eed1c6604d6a4dcf69c4b05950b12f3664701713fb091ee714e5c:p:21f5e16bdaeb93e40ddd5bcd4cf8da7001f4ac39c71082a8b4fd9d3163b04a4c`；passage 本身匹配 evidence：False。
- Rank 5：`european-xfel-full-technical-design-report-2007:4fcb555cc63e04dbb22a81728ae9d0803ed38a23f083a36ee309806f48e8aaed`，第 242 页；score 0.5313；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:4fcb555cc63e04dbb22a81728ae9d0803ed38a23f083a36ee309806f48e8aaed:p:a2b9bb836a5a5dd209659178b471ee0f9cc248e08cb602dc2143e59474d12ad9`；passage 本身匹配 evidence：False。

#### shine-ioc-management

完整父 Chunk 证据首次排名：4；仅按获胜 passage 判断的完整证据首次排名：4。

- Rank 1：`shine-epics-ioc-pv-information-management-pcapac2022:dbbe5b3ca2a4ae4ff7f7debebe9fc61aa28441bfff953e06bf43c18deaa03696`，第 1 页；score 0.5862；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:dbbe5b3ca2a4ae4ff7f7debebe9fc61aa28441bfff953e06bf43c18deaa03696:p:71e4cfd84990ac396aed058e49c317a3cbe820432befcf05329714f743b85e5d`；passage 本身匹配 evidence：False。
- Rank 2：`shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355`，第 2 页；score 0.5763；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355:p:84e4346df0804414c4f53f45cb4b61d40484e671826b2299c795cd35c2f6e3e6`；passage 本身匹配 evidence：False。
- Rank 3：`shine-epics-ioc-pv-information-management-pcapac2022:6b532252b1d9b5d12ff2e3846095924490c1864b4f7f864b57d511bf95da5bd2`，第 1 页；score 0.5749；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:6b532252b1d9b5d12ff2e3846095924490c1864b4f7f864b57d511bf95da5bd2:p:3b7255adf796d12da077b88b0bcb0f1c7d65f6fe011c00064812e3f385458b76`；passage 本身匹配 evidence：True。
- Rank 4：`shine-epics-ioc-pv-information-management-pcapac2022:05aa96b5b26bfd6d0f4d87026ad1cab08e601e88fd24b542639ee2769c362092`，第 1 页；score 0.5589；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:05aa96b5b26bfd6d0f4d87026ad1cab08e601e88fd24b542639ee2769c362092:p:834f38043e04ea458f6bce2895b12b401346771e084711e7fb353adc89809a87`；passage 本身匹配 evidence：True。
- Rank 5：`shine-epics-ioc-pv-information-management-pcapac2022:d4af88117b4bd2142e2bc98d5499c099b12a7ece2d2382770f83de9ba80e907d`，第 2 页；score 0.5519；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:d4af88117b4bd2142e2bc98d5499c099b12a7ece2d2382770f83de9ba80e907d:p:0d4236e0103be1c35844827fd205826685d13282dcdbcc1dbb2c94325e2d2cdc`；passage 本身匹配 evidence：False。

#### shine-ioc-startup

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996`，第 28 页；score 0.5361；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:7fea3c0866c750c74466235f789309d88896e2ac489d7f5bbaeaea5ad97b5996:p:802001c9a48b02c86c319634fb3fd31e9fa063b6961036d9a08737fc3003e81c`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9`，第 10 页；score 0.5261；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:79ceee5073b226d43b0d5d38f53e6bc5ae29c1a4a73ef219021e3def271bdfe9:p:18c75026e239b15ce6b090b5daad7b09cbdf52fa5025e9ab6b8e062f83b037a7`；passage 本身匹配 evidence：False。
- Rank 3：`shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355`，第 2 页；score 0.5248；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:cdb4a73a10acf985b22603c61315537abad1221be890ead9d73ed16c180e4355:p:84e4346df0804414c4f53f45cb4b61d40484e671826b2299c795cd35c2f6e3e6`；passage 本身匹配 evidence：True。
- Rank 4：`shine-epics-ioc-pv-information-management-pcapac2022:dbbe5b3ca2a4ae4ff7f7debebe9fc61aa28441bfff953e06bf43c18deaa03696`，第 1 页；score 0.5160；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:dbbe5b3ca2a4ae4ff7f7debebe9fc61aa28441bfff953e06bf43c18deaa03696:p:71e4cfd84990ac396aed058e49c317a3cbe820432befcf05329714f743b85e5d`；passage 本身匹配 evidence：False。
- Rank 5：`shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981`，第 3 页；score 0.5110；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-epics-ioc-pv-information-management-pcapac2022:1932c96141925c86a65dfa6e099ba4ccedb9d73bc4a8de6a17d5d405d2544981:p:db9b74c61608d6f8c1d4d0f57091452b228199702662785fc694f74785e0a9f8`；passage 本身匹配 evidence：False。

#### cryo-interlock

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-cryogenic-control-system-2021:ddacec98352d4a3364b0ed059ee45daccd318912026ba96e0e2849bf8bc6de8d`，第 6 页；score 0.5281；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-cryogenic-control-system-2021:ddacec98352d4a3364b0ed059ee45daccd318912026ba96e0e2849bf8bc6de8d:p:4833469576c3fe84196710fee9a7168465b0a5af186ec669afa3ada8d72d2708`；passage 本身匹配 evidence：True。
- Rank 2：`shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe`，第 277 页；score 0.4822；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:338c3be071bf2a8399235ffed40dad15708f2233eb7307fba06d901fda6a4bfe:p:e5dba046e8063dfbec0df22763937a82b7cec1c15ff28131fe5aea510e10c44b`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-preliminary-design-report-2017:90978b5dd35c9a8198a73fbe358f5215d18644ad865b44c89d5f9cdc7baed421`，第 276 页；score 0.4707；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:90978b5dd35c9a8198a73fbe358f5215d18644ad865b44c89d5f9cdc7baed421:p:83417fe18b9e53a4889d5874cb18a06b10acac97095a9596151398b86636338a`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120`，第 3 页；score 0.4630；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:3989f77d1ed901e922429b49a72751dc4b71b50fb0267e5c7a8fe005090a5120:p:48e89f96feeb4448e9f8fc38a38511a2fbb7ec5006808a33be5f0107567a677c`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b`，第 2 页；score 0.4497；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:ebd5cee20ea18f316baa2e89475b57b8ed49501badf8ce257719cd5aa532225b:p:feadd1b4de0b18c496365489de64035a32d3a3bd45309c1439762e2f9e415ffd`；passage 本身匹配 evidence：False。

#### shine-compressors

完整父 Chunk 证据首次排名：3；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-white-rabbit-beam-synchronous-timing-ipac2022:044f7bc2b3e46bebdd43195cac2d05a60087e6df478e1a3f889082ae9933217e`，第 1 页；score 0.4772；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-white-rabbit-beam-synchronous-timing-ipac2022:044f7bc2b3e46bebdd43195cac2d05a60087e6df478e1a3f889082ae9933217e:p:778addfecda0ed847fe743916c3a27344d37090de3a86f66143a05f1ddb00961`；passage 本身匹配 evidence：False。
- Rank 2：`european-xfel-full-technical-design-report-2007:016d98b224253008fd275a2500c89a07c410baf79b6eb617ae0a21216e8583b3`，第 41 页；score 0.4722；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:016d98b224253008fd275a2500c89a07c410baf79b6eb617ae0a21216e8583b3:p:07f71c868a15b66a8a025615b81e0db4fe1b8c81d4bb974e87de13ff7e2bce57`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3`，第 61 页；score 0.4568；父 Chunk 匹配至少一组 evidence：True；获胜 passage `shine-accelerator-preliminary-design-report-2017:485d8b33ff6ed2e347fa8cba06c82d98aeec1523072c4601be8da25fc12826a3:p:c965eabf3fdf5894f376589b130f7db311200c96cf487c93dc4620d076e62cf9`；passage 本身匹配 evidence：False。
- Rank 4：`european-xfel-full-technical-design-report-2007:30a4e3d6152ae95d08fa15bd5039e51733133feae5143133c310afce0b0b9f22`，第 589 页；score 0.4542；父 Chunk 匹配至少一组 evidence：False；获胜 passage `european-xfel-full-technical-design-report-2007:30a4e3d6152ae95d08fa15bd5039e51733133feae5143133c310afce0b0b9f22:p:93e98a972abc3f1c0bc4231ab48fcb78825b7afb9c89e85946c2ab090358aa29`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-preliminary-design-report-2017:f6e76b2a09cf44300cf833f8f28562d70ee4b49d47378bd760e38a531596a02c`，第 69 页；score 0.4507；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-preliminary-design-report-2017:f6e76b2a09cf44300cf833f8f28562d70ee4b49d47378bd760e38a531596a02c:p:bad70c1d94623a31870c83128d1d2b9c94d8a69a56419cac73afc67e3e848946`；passage 本身匹配 evidence：False。

#### shine-main-linac

完整父 Chunk 证据首次排名：None；仅按获胜 passage 判断的完整证据首次排名：None。

- Rank 1：`shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520`，第 6 页；score 0.5578；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:028145fdcf7f3c6b61a4f50c060f8cf74bff6a85e1b0e1b1d9ae736b70167520:p:239f0a87ef4444a973b5535e6338e3a796a76c72eb5ae31aad898dd799ef2ba2`；passage 本身匹配 evidence：False。
- Rank 2：`shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8`，第 5 页；score 0.5444；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:fb77460ddb53b1eaa6ea406ddceba2e11119bad8231d16f4a443c62a063769c8:p:f2f7b6393b693816a51cabd398bdd2720a13e2573ac5e6e5fc1baca4bb448061`；passage 本身匹配 evidence：False。
- Rank 3：`shine-accelerator-control-system-design-presentation:68069a99c611a15e8ebbcd6a55ae0ba6c85a0e647383102dc533492844c312b2`，第 3 页；score 0.5282；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:68069a99c611a15e8ebbcd6a55ae0ba6c85a0e647383102dc533492844c312b2:p:fb23db351f06ada4bfeb4a91e37ff23bba0715f28a4d6e4124ac92674bcf820d`；passage 本身匹配 evidence：False。
- Rank 4：`shine-accelerator-control-system-design-presentation:21f0da3ba0bfd9829b5d9d2f464ff9233c8628182972b7e88f8707e09c84d533`，第 4 页；score 0.5196；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-control-system-design-presentation:21f0da3ba0bfd9829b5d9d2f464ff9233c8628182972b7e88f8707e09c84d533:p:b1ca4dddffc0313a832fff0c9530d32e7c18da60c93a69f29b3b39eb11dc30ae`；passage 本身匹配 evidence：False。
- Rank 5：`shine-accelerator-fast-interlock-2024:508e70c7e7387d951a35f023453d08ca74510b203abf6484060010eea25c6779`，第 6 页；score 0.5183；父 Chunk 匹配至少一组 evidence：False；获胜 passage `shine-accelerator-fast-interlock-2024:508e70c7e7387d951a35f023453d08ca74510b203abf6484060010eea25c6779:p:15767b78c2cd81426b23ea70561975dd0ec87108d862ebc0372090b1c191feab`；passage 本身匹配 evidence：False。

## 人工证据复核与解释限制

E5 的收益主要来自英文同语言检索：英文 Hit@5 从 BGE-small 的 6/13 提高到 12/13；中文从 3/8 提高到 4/8。总体从 9/21 提高到 16/21，Hit@1 从 2/21 提高到 6/21。这支持 BGE-small 是当前英文 Dense 质量的重要瓶颈，但不能把全部问题归因于模型权重。比较对象包含各模型的 tokenizer 和正式编码契约。

跨语言的完整命中均为 0/3，但不能把三种模型的行为视为相同。xfel-normal-energy：BGE-small 和 E5 返回中文 SHINE 内容；BGE-base 返回英文 XFEL 目标文档，却未找到指定常规能量证据。shine-ioc-startup：BGE-base 第 3 名找到目标英文论文第 2 页，满足 1/2 证据组；另两模型为 0/2。cryo-interlock：BGE-base 第 1 名找到目标英文论文第 6 页，满足 master PLC 与 CPLD 两组证据，缺 DI/DO 组，共 2/3；另两模型为 0/3。完整首次排名均仍为空，正式指标不变。

xfel-rf：E5 第 5 名的第 65 页 passage 同时包含 1.3 GHz 与 20 GeV 的所需证据，是真实新增完整命中。shine-ioc-management：BGE-base 第 4 名完成全部证据组，获胜 passages 也完成契约；E5 只找到部分证据，仍为未完整命中。

shine-compressors：E5 第 4 名的获胜 passage 覆盖完整指定摘录。BGE-base 第 3 名返回正确父 Chunk，但最高分 passage 未完整覆盖长摘录；first_complete_passage_rank 为空。正式 parent 指标仍接受 BGE-base 的命中，因为结果会恢复完整 canonical parent。

shine-main-linac 存在冻结证据覆盖不足。已独立核对原始 PDF：同一份初步设计报告第 60 页及 E5 Top-1 父 Chunk 同时包含超导连续波模式与最终 8 GeV。最高分 passage 包含终能量，完整父 Chunk 还包含工作模式。契约只接受第 5 页指定摘录，所以正式 first_complete_rank 仍为空。不能把该例简单解释为检索到错误内容，也不能把正式 BM25-only 标签直接当作 E5 缺少答案证据的证明。未改 ground truth 或重算指标。

负例分数只在各模型内部解释。E5 answerable Top-1 中位数为 0.8821，hard-domain 最大值为 0.8826，范围存在重叠。BGE-small 与 BGE-base 同样存在 answerable/hard-domain 分布重叠。三个模型都向全部 11 条负例返回结果；未设置 threshold。不能因跨模型 cosine 数字更高就判定模型更差，也不能把高相似度当作答案存在的证明。

新候选在同一 CPU 上统一使用 6 个线程、batch size 32。首次完整语料 embedding：E5 1,344.92 s，BGE-base 1,433.42 s。BGE-small 复用 Stage 2.6 向量，其历史 embedding 为 524.86 s；旧 JSON 未独立记录线程数，旧运行手册命令为 2 个线程。历史耗时仅作成本参考，不直接计算严格性能倍率。中止的 E5 两线程试运行另行记录，约 278.41 s、448 条 passage，不混入完整六线程计时。

BM25 与 E5 当前 Top-5 覆盖并集为 17/21；与 BGE-base 的并集也为 17/21，但新增 query 不同。这是集合覆盖上界，不是 Hybrid 实测结果。全部三条跨语言查询仍未完整覆盖。只有 21 条 answerable，所有总体与切片仅作诊断，不作显著性或跨语料泛化结论。

## 模型两两比较

比较 first_complete_rank，双双缺失记为 same。

```json
[
  {
    "model_a": "BAAI/bge-small-zh-v1.5",
    "model_b": "intfloat/multilingual-e5-base",
    "basis": "first_complete_rank; missing=outside Top-5",
    "counts": {
      "a_wins": 2,
      "b_wins": 12,
      "same": 7
    },
    "query_ids": {
      "a_wins": [
        "xfel-bpm-types",
        "interlock-latency"
      ],
      "b_wins": [
        "epics-pp",
        "epics-reconnect",
        "epics-cli",
        "xfel-rf",
        "undulator-tuning",
        "xfel-mirror-angle",
        "xfel-soft-mono",
        "shine-control-layers",
        "cryo-integration",
        "timing-wrtd",
        "timing-jitter",
        "shine-compressors"
      ],
      "same": [
        "xfel-normal-energy",
        "shine-ioc-management",
        "shine-ioc-startup",
        "interlock-platform",
        "cryo-interlock",
        "control-slow-interlock",
        "shine-main-linac"
      ]
    }
  },
  {
    "model_a": "BAAI/bge-small-zh-v1.5",
    "model_b": "BAAI/bge-base-zh-v1.5",
    "basis": "first_complete_rank; missing=outside Top-5",
    "counts": {
      "a_wins": 3,
      "b_wins": 8,
      "same": 10
    },
    "query_ids": {
      "a_wins": [
        "epics-reconnect",
        "interlock-latency",
        "control-slow-interlock"
      ],
      "b_wins": [
        "epics-pp",
        "epics-cli",
        "undulator-tuning",
        "xfel-mirror-angle",
        "shine-ioc-management",
        "shine-control-layers",
        "timing-wrtd",
        "shine-compressors"
      ],
      "same": [
        "xfel-rf",
        "xfel-normal-energy",
        "xfel-soft-mono",
        "xfel-bpm-types",
        "shine-ioc-startup",
        "interlock-platform",
        "cryo-integration",
        "cryo-interlock",
        "timing-jitter",
        "shine-main-linac"
      ]
    }
  },
  {
    "model_a": "intfloat/multilingual-e5-base",
    "model_b": "BAAI/bge-base-zh-v1.5",
    "basis": "first_complete_rank; missing=outside Top-5",
    "counts": {
      "a_wins": 9,
      "b_wins": 3,
      "same": 9
    },
    "query_ids": {
      "a_wins": [
        "epics-pp",
        "epics-reconnect",
        "xfel-rf",
        "xfel-mirror-angle",
        "xfel-soft-mono",
        "cryo-integration",
        "timing-wrtd",
        "timing-jitter",
        "control-slow-interlock"
      ],
      "b_wins": [
        "xfel-bpm-types",
        "shine-ioc-management",
        "shine-compressors"
      ],
      "same": [
        "epics-cli",
        "xfel-normal-energy",
        "undulator-tuning",
        "shine-ioc-startup",
        "interlock-latency",
        "interlock-platform",
        "shine-control-layers",
        "cryo-interlock",
        "shine-main-linac"
      ]
    }
  }
]
```

## 结论

推荐 intfloat/multilingual-e5-base 作为当前单 Dense 的选型。它的 Hit@1、Hit@5 和 MRR@5 均最好；相对 BGE-small 新增 7 条完整命中，英文 Hit@5 达 12/13。xfel-rf 与 shine-compressors 的获胜 passage 均含完整 required evidence。相对 BGE-base，E5 同为 768 维，实测完整编码耗时相近且略低，却有更好的总体质量。代价是本地模型文件约 1,082 MiB，明显大于 BGE-base 的约 391 MiB 和 BGE-small 的约 92 MiB。E5 并非逐条占优：BGE-base 在 IOC management、部分跨语言证据覆盖和若干排名上更好。

下一阶段选择 B：继续 Dense representation/model investigation。优先定位三条跨语言查询的目标证据排名与完整证据组覆盖，并复核已发现的冻结证据覆盖不足。E5 相对 BM25 有 2 条真实独立命中，但完整 cross-language 仍为 0/3；BGE-base 的部分跨语言命中说明，剩余问题包含证据覆盖与排序，而不只是完全无法跨语言对齐。当前 Top-5 互补数据不足以证明 RRF 能解决这些缺口。RRF 对整体排序的潜在收益可在后续独立验证，本轮不实现。

## 验证

- `pytest -q`：275 passed。
- `ruff check .`：通过。
- `git diff --check`：通过。
- `python scripts/corpus_inventory.py`：13 份 registered PDFs，validation OK。
- 三个 persistent 索引重复运行：fingerprint、point count、全部排名和指标一致，语料重编码数为 0。
- 13 份原始 PDF、冻结查询集、7 个关键实现文件与 Stage 2.6 指纹相同；历史 Stage 2.6 JSON 未改动。

全部 Top-5 parents、获胜 passage 全文、score、证据组判断、完整模型文件指纹和验证记录保存在同名 JSON。
