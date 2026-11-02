#!/usr/bin/env python3
"""Validate a knowledge-base release manifest without touching a release.

An incomplete candidate may omit indexes and a rollback target, but any manifest
that claims ``accepted`` or ``live`` must have both index builds, verification
records and a verified rollback target.  Credentials are rejected everywhere.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


STATUSES = {
    "candidate-incomplete",
    "candidate",
    "accepted",
    "live",
    "rolled_back",
    "retired",
}
COMPLETE_STATUSES = {"accepted", "live", "rolled_back", "retired"}
_SECRET_KEYS = re.compile(
    r"(?:^|_)(?:secret|password|passwd|credential|api_?key|"
    r"access_token|refresh_token|private_key|token)$",
    re.IGNORECASE,
)
_RELEASE_ID = re.compile(r"^kb-\d+\.\d+\.\d+(?:-rc\.\d+)?$")
_BUILD_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REQUIRED = {
    "schema_version",
    "release_id",
    "build_id",
    "status",
    "created_at",
    "registry",
    "code",
    "corpus",
    "contracts",
    "indexes",
    "answer",
    "verification",
    "operations",
}


def _walk(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else key
            yield key_path, key
            yield from _walk(item, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def _walk_strings(value, path=""):
    if isinstance(value, str):
        yield path or "$", value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")


def validate(payload: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ["manifest 根节点必须是 JSON 对象"], []
    missing = sorted(_REQUIRED - set(payload))
    if missing:
        errors.append("缺少顶层字段: " + ", ".join(missing))
    if payload.get("schema_version") != 2:
        errors.append("schema_version 必须为 2")
    release_id = payload.get("release_id", "")
    if not isinstance(release_id, str) or not _RELEASE_ID.fullmatch(release_id):
        errors.append("release_id 必须形如 kb-2.0.0 或 kb-2.0.0-rc.1")
    status = payload.get("status")
    build_id = payload.get("build_id", "")
    placeholder_build = isinstance(build_id, str) and build_id.startswith("<")
    if placeholder_build and status == "candidate-incomplete":
        warnings.append("模板 build_id 仍为占位符")
    elif not isinstance(build_id, str) or not _BUILD_ID.fullmatch(build_id):
        errors.append("build_id 必须是小写 slug")
    if status not in STATUSES:
        errors.append(f"status 必须是 {sorted(STATUSES)} 之一")
    created_at = payload.get("created_at", "")
    if isinstance(created_at, str) and not created_at.startswith("<"):
        try:
            datetime.strptime(created_at, "%Y-%m-%d")
        except ValueError:
            errors.append("created_at 必须是 YYYY-MM-DD")
    for path, key in _walk(payload):
        if _SECRET_KEYS.search(key):
            errors.append(f"疑似凭据字段: {path}")

    code = payload.get("code")
    if not isinstance(code, dict):
        errors.append("code 必须是对象")
    elif not isinstance(code.get("git_commit"), str) or not code["git_commit"]:
        errors.append("code.git_commit 不能为空")
    elif code["git_commit"].startswith("<") and status == "candidate-incomplete":
        warnings.append("模板 code.git_commit 仍为占位符")

    if status in COMPLETE_STATUSES:
        for path, value in _walk_strings(payload):
            if "<" in value or ">" in value:
                errors.append(f"完整发布不能包含占位符: {path}={value!r}")

    corpus = payload.get("corpus")
    if not isinstance(corpus, dict):
        errors.append("corpus 必须是对象")
    else:
        for key in ("revision_count", "total_chunks", "eligible_chunks"):
            value = corpus.get(key)
            if type(value) is not int or value < 0:
                errors.append(f"corpus.{key} 必须是非负整数")
        if status in COMPLETE_STATUSES:
            for key in ("revision_count", "total_chunks", "eligible_chunks"):
                if corpus.get(key, 0) <= 0:
                    errors.append(f"完整发布的 corpus.{key} 必须大于 0")
            if corpus.get("allow_missing_source") is not False:
                errors.append("完整发布不能使用 allow_missing_source")
            counts = corpus.get("parse_status_counts")
            if isinstance(counts, dict):
                for failed_status in ("failed", "missing_source", "pending_ocr"):
                    if counts.get(failed_status, 0):
                        errors.append(
                            f"完整发布仍有 {failed_status}={counts[failed_status]}"
                        )

    contracts = payload.get("contracts")
    if not isinstance(contracts, dict):
        errors.append("contracts 必须是对象")
    elif contracts.get("schema_version") != 2:
        errors.append("contracts.schema_version 必须为 2")

    indexes = payload.get("indexes")
    if not isinstance(indexes, list):
        errors.append("indexes 必须是数组")
        indexes = []
    if status in COMPLETE_STATUSES:
        if len(indexes) != 2:
            errors.append("完整发布必须包含两路索引")
        for index, item in enumerate(indexes):
            if not isinstance(item, dict):
                errors.append(f"indexes[{index}] 必须是对象")
                continue
            for key in ("model_name", "collection", "index_path"):
                if not isinstance(item.get(key), str) or not item[key].strip():
                    errors.append(f"indexes[{index}] 缺少 {key}")
            if not isinstance(item.get("dense_index_contract_id"), str) or not item[
                "dense_index_contract_id"
            ]:
                errors.append(f"indexes[{index}] 缺少 dense_index_contract_id")
            for key in ("parent_count", "point_count"):
                if type(item.get(key)) is not int or item[key] <= 0:
                    errors.append(f"indexes[{index}].{key} 必须为正整数")
        if len(indexes) == 2:
            models = {
                item.get("model_name") for item in indexes if isinstance(item, dict)
            }
            contracts = {
                item.get("dense_index_contract_id")
                for item in indexes
                if isinstance(item, dict)
            }
            if len(models) != 2:
                errors.append("两路索引必须使用不同模型")
            if len(contracts) != 2:
                errors.append("两路索引必须使用不同 DenseIndexContract")

    verification = payload.get("verification")
    operations = payload.get("operations")
    if not isinstance(verification, dict):
        errors.append("verification 必须是对象")
    if not isinstance(operations, dict):
        errors.append("operations 必须是对象")
    if status in COMPLETE_STATUSES:
        required_verification = {
            "engineering_report",
            "semantic_review_owner",
            "performance_baseline",
            "rollback_drill",
        }
        missing_verification = sorted(
            key
            for key in required_verification
            if not isinstance(verification.get(key), str) or not verification[key].strip()
        )
        if missing_verification:
            errors.append(
                "完整发布缺少 verification 记录: "
                + ", ".join(missing_verification)
            )
        if not isinstance(operations.get("rollback_target"), str) or (
            operations["rollback_target"] in {"", "unknown"}
        ):
            errors.append("完整发布必须有明确 rollback_target")
        if operations.get("rollback_verified") is not True:
            errors.append("完整发布必须完成回滚演练")
    else:
        if not indexes:
            warnings.append("候选未包含索引；状态必须保持 candidate-incomplete")
        if operations.get("rollback_target") in {None, "", "unknown"}:
            warnings.append("候选没有回滚目标；不得标记为 accepted/live")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read manifest: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate(payload)
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "release_id": payload.get("release_id"),
                "build_id": payload.get("build_id"),
                "warnings": len(warnings),
                "errors": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
