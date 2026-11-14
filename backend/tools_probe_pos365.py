#!/usr/bin/env python3
"""Dò API POS365 thật để chốt các điểm PDF không nói (D08, D09, D19).

Chạy:  python backend/tools_probe_pos365.py [--pages 3] [--try-filter 2026-11-01] [--out probe.json]
Đọc cấu hình từ biến môi trường (xem .env.live.example): POS365_BASE_URL, POS365_USERNAME/PASSWORD
hoặc POS365_AUTH_MODE=none + POS365_EXTRA_HEADERS.

Báo cáo CHỈ chứa cấu trúc (tên trường, đếm theo Status, thứ tự thời gian, số dòng tổng), KHÔNG chứa tên khách,
tên bàn hay mã đơn, để có thể đính kèm vào docs/ làm căn cứ mà không lộ dữ liệu thật.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from backend.app.config import AppConfig  # noqa: E402
from backend.app.services.pos365 import Pos365Client, Pos365Error, TOTAL_ROW_CODE, TOTAL_ROW_ID  # noqa: E402


def probe(client: Pos365Client, pages: int = 3, page_size: int = 20, try_filter: str | None = None) -> dict:
    report: dict = {"page_size": page_size, "pages_fetched": 0}
    rows: list = []
    count = None
    for n in range(pages):
        payload = client.get_orders_page(page_size, n * page_size)
        report["pages_fetched"] += 1
        if count is None:
            count = payload.get("__count")
        batch = payload.get("results") or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
    report["__count"] = count
    report["rows_fetched"] = len(rows)
    report["top_level_keys"] = sorted({k for r in rows for k in r})
    report["status_values"] = dict(Counter(str(r.get("Status")) for r in rows))
    report["total_like_rows"] = sum(1 for r in rows if r.get("Id") == TOTAL_ROW_ID or r.get("Code") == TOTAL_ROW_CODE)
    stamps = [r["PurchaseDate"] for r in rows if r.get("PurchaseDate")]
    report["purchase_date_suffix_z"] = bool(stamps) and all(s.endswith("Z") for s in stamps)
    if len(stamps) >= 2:
        report["order_of_results"] = ("giảm dần" if stamps[0] > stamps[-1] else
                                      "tăng dần" if stamps[0] < stamps[-1] else "không rõ")
    report["code_prefixes"] = dict(Counter("".join(c for c in str(r.get("Code", ""))[:3] if c.isalpha())
                                           for r in rows))
    if try_filter:
        # D09: thử cú pháp OData; chỉ báo cách nào làm __count thay đổi, không suy diễn thêm
        results = {}
        for name, query in {"odata_filter": f"$filter=PurchaseDate ge datetime'{try_filter}T00:00:00Z'",
                            "plain_param": f"FromDate={try_filter}"}.items():
            try:
                url_payload = client._open(  # noqa: SLF001 (công cụ dò, cố ý dùng tầng thấp)
                    f"{client.base_url}/api/orders?format=json&{client.top_param}=1&{client.skip_param}=0&{query}",
                    client._headers())  # noqa: SLF001
                data = client._json(*url_payload, "/api/orders (thử lọc)")  # noqa: SLF001
                results[name] = {"count": data.get("__count"), "changed": data.get("__count") != count}
            except Pos365Error as exc:
                results[name] = {"error": str(exc)[:120]}
        report["date_filter_probe"] = results
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--try-filter", metavar="YYYY-MM-DD")
    ap.add_argument("--out")
    args = ap.parse_args()
    cfg = AppConfig.from_env()
    if not cfg.pos365_base_url:
        print("Thiếu POS365_BASE_URL", file=sys.stderr)
        return 2
    client = Pos365Client(cfg.pos365_base_url, os.environ.get("POS365_USERNAME", ""),
                          os.environ.get("POS365_PASSWORD", ""), cfg.pos365_auth_mode, cfg.pos365_extra_headers,
                          cfg.pos365_top_param, cfg.pos365_skip_param)
    try:
        report = probe(client, args.pages, cfg.pos365_page_size, args.try_filter)
    except Pos365Error as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
