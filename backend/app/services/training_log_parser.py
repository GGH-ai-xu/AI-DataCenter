from __future__ import annotations

import os
import re


LOG_FILE_PATTERNS = (
    "*.log",
    "train*.log",
    "output*.log",
    "nohup.out",
    "training.log",
    "train.log",
    "log.txt",
    "*.out",
)
TRAINING_KEYWORDS = (
    "python",
    "train",
    "training",
    "torchrun",
    "deepspeed",
    "accelerate",
    "notebook",
    "jupyter",
    "tensorboard",
)
METRIC_PATTERNS = (
    re.compile(
        r"[Ee]poch\s*[:\s]?\s*(\d+)(?:\s*/\s*\d+)?"
        r".*?[Ll]oss\s*[:\s=]\s*([\d.]+(?:e[+-]?\d+)?)"
        r"(?:.*?[Aa]cc(?:uracy)?\s*[:\s=]\s*([\d.]+))?"
    ),
    re.compile(
        r"\[?\s*[Ee]poch\s+(\d+)\s*\]?"
        r".*?(?:train_?)?loss\s*[=:]\s*([\d.]+(?:e[+-]?\d+)?)"
        r"(?:.*?(?:val_?)?(?:acc|accuracy)\s*[=:]\s*([\d.]+))?"
    ),
    re.compile(
        r"(?:[Ss]tep|[Ii]ter(?:ation)?)\s*[:\s]?\s*(\d+)"
        r".*?[Ll]oss\s*[:\s=]\s*([\d.]+(?:e[+-]?\d+)?)"
        r"(?:.*?[Aa]cc(?:uracy)?\s*[:\s=]\s*([\d.]+))?"
    ),
)
MAX_METRICS = 200


def parse_training_metrics(raw: str) -> list[dict]:
    metrics = []
    seen_epochs = set()
    for line in raw.splitlines():
        for pattern in METRIC_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            epoch = int(match.group(1))
            if epoch in seen_epochs:
                break
            seen_epochs.add(epoch)
            entry = {"epoch": epoch, "loss": float(match.group(2))}
            if match.group(3):
                entry["accuracy"] = float(match.group(3))
            metrics.append(entry)
            break
    metrics.sort(key=lambda item: item["epoch"])
    return metrics[-MAX_METRICS:]


def looks_like_training_process(
    process: dict,
    cwd: str,
    log_files: list[str],
) -> bool:
    text_parts = [
        str(process.get("name", "")).lower(),
        str(process.get("command", "")).lower(),
        str(cwd or "").lower(),
        " ".join(os.path.basename(path).lower() for path in log_files),
    ]
    joined = " ".join(part for part in text_parts if part)
    return any(keyword in joined for keyword in TRAINING_KEYWORDS)
