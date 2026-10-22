"""Download only the two authorized Stage 2.8 embedding candidates."""

from huggingface_hub import snapshot_download

for name in ["BAAI/bge-m3", "Qwen/Qwen3-Embedding-0.6B"]:
    try:
        path = snapshot_download(
            name,
            local_dir="tmp/stage-two-eight/models/" + name.replace("/", "--"),
            allow_patterns=[
                "*.json",
                "*.safetensors",
                "pytorch_model.bin",
                "tokenizer*",
                "vocab*",
                "merges*",
                "sentencepiece*",
                "*.model",
                "README.md",
            ],
            ignore_patterns=["onnx/*", "openvino/*"],
            max_workers=2,
        )
        print("DOWNLOADED", name, path, flush=True)
    except Exception as exc:
        print("DOWNLOAD_FAILED", name, type(exc).__name__, str(exc), flush=True)
