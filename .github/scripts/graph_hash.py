"""graph.json 내용 해시 (meta.built_at 제외) — 실질 변경 여부 판단용."""
import hashlib
import json
import sys

try:
    with open("data/graph.json", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print("none")
    sys.exit(0)

data.get("meta", {}).pop("built_at", None)  # 빌드 시각은 매번 바뀌므로 제외
blob = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
print(hashlib.md5(blob).hexdigest())
