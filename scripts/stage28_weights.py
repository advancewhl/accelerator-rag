"""Resumable ranged download of the two explicitly authorized weight files."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
import time
import httpx
from huggingface_hub import get_hf_file_metadata, hf_hub_url

for repo, filename in [
    ("BAAI/bge-m3", "pytorch_model.bin"),
    ("Qwen/Qwen3-Embedding-0.6B", "model.safetensors"),
]:
    local = Path("tmp/stage-two-eight/models") / repo.replace("/", "--")
    metadata = get_hf_file_metadata(hf_hub_url(repo, filename))
    parts = local / ".weight-parts"
    parts.mkdir(exist_ok=True)
    width = 32 * 1024 * 1024
    spans = [
        (i, min(i + width, metadata.size) - 1) for i in range(0, metadata.size, width)
    ]
    started = time.monotonic()

    def download(span):
        start, end = span
        path = parts / str(start)
        if path.exists() and path.stat().st_size == end - start + 1:
            return
        for attempt in range(4):
            try:
                with httpx.Client(follow_redirects=True, timeout=120) as client:
                    with client.stream(
                        "GET",
                        metadata.location,
                        headers={"Range": f"bytes={start}-{end}"},
                    ) as response:
                        response.raise_for_status()
                        if (
                            response.status_code != 206
                            or response.headers.get("content-range")
                            != f"bytes {start}-{end}/{metadata.size}"
                        ):
                            raise ValueError("unexpected server range")
                        with path.open("wb") as stream:
                            for block in response.iter_bytes(1024 * 1024):
                                stream.write(block)
                if path.stat().st_size != end - start + 1:
                    raise ValueError("partial range")
                return
            except Exception:
                if attempt == 3:
                    raise

    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, future in enumerate(
            as_completed([pool.submit(download, s) for s in spans]), 1
        ):
            future.result()
            print(
                repo,
                "parts",
                i,
                "/",
                len(spans),
                "seconds",
                round(time.monotonic() - started),
                flush=True,
            )
    output = local / (filename + ".assembling")
    digest = sha256()
    with output.open("wb") as stream:
        for start, _ in spans:
            with (parts / str(start)).open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    stream.write(block)
                    digest.update(block)
    if digest.hexdigest() != metadata.etag:
        raise ValueError("official weight SHA256 mismatch")
    output.replace(local / filename)
    (local / "weights-download-provenance.json").write_text(
        __import__("json").dumps(
            {
                "repo": repo,
                "file": filename,
                "revision": metadata.commit_hash,
                "size": metadata.size,
                "sha256": digest.hexdigest(),
            },
            indent=2,
        )
    )
    for part in parts.iterdir():
        part.unlink()
    parts.rmdir()
    print("VERIFIED", repo, digest.hexdigest(), flush=True)
