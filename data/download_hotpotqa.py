"""
HotpotQA 데이터셋 다운로드 스크립트
저장 경로: data/raw/
"""

import os
import json
from datasets import load_dataset

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")


def download_hotpotqa():
    os.makedirs(RAW_DIR, exist_ok=True)

    print("HotpotQA 다운로드 중 (distractor 설정)...")
    dataset = load_dataset("hotpot_qa", "distractor")

    for split in ("train", "validation"):
        out_path = os.path.join(RAW_DIR, f"hotpotqa_{split}.json")
        records = [dict(row) for row in dataset[split]]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"  {split}: {len(records)}건 저장 → {out_path}")

    print("완료.")


if __name__ == "__main__":
    download_hotpotqa()
