"""EDINET 書類取得API CSV(type=5) のパース。

CSV は UTF-16 / タブ区切り。列は
  要素ID / 項目名 / コンテキストID / 相対年度 / 連結・個別 / 期間・時点 /
  ユニットID / 単位 / 値
「主要な経営指標等の推移」は 1 書類に5年ぶん入っており、コンテキストIDが
  CurrentYearDuration / Prior1YearDuration ... Prior4YearDuration
のように相対年度で分かれている（個別は _NonConsolidatedMember が付く）。
"""
from __future__ import annotations

import csv
import io
import zipfile

from common import to_float
from edinet import ensure_csv_zip

# 相対年度（新しい→古い）
DUR_CONTEXTS = ["CurrentYearDuration", "Prior1YearDuration", "Prior2YearDuration",
                "Prior3YearDuration", "Prior4YearDuration"]
INST_CONTEXTS = ["CurrentYearInstant", "Prior1YearInstant", "Prior2YearInstant",
                 "Prior3YearInstant", "Prior4YearInstant"]

META_ELEMENTS = {
    "FilerNameInJapaneseDEI": "filer_name",
    "CurrentFiscalYearStartDateDEI": "period_start",
    "CurrentFiscalYearEndDateDEI": "period_end",
    "SecurityCodeDEI": "seccode",
    "EDINETCodeDEI": "edinet_code",
}


def _local(element: str) -> str:
    """要素ID から名前空間接頭辞を落とす。 jppfs_cor:NetSales -> NetSales"""
    return element.split(":")[-1]


class Doc:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.meta: dict[str, str] = {"doc_id": doc_id}
        # local要素名 -> { コンテキストID -> 値(str) }
        self._by_name: dict[str, dict[str, str]] = {}

    # -- 低レベル -------------------------------------------------

    def _cell(self, local_name: str, context: str) -> str | None:
        return self._by_name.get(local_name, {}).get(context)

    def num(self, names: str | list[str], context: str,
            *, consolidated_first: bool = True) -> float | None:
        """候補要素名リストを順に試し、連結→個別の順で最初の数値を返す。"""
        if isinstance(names, str):
            names = [names]
        suffixes = ["", "_NonConsolidatedMember"] if consolidated_first \
            else ["_NonConsolidatedMember", ""]
        for name in names:
            ctxs = self._by_name.get(name)
            if not ctxs:
                continue
            for suf in suffixes:
                v = to_float(ctxs.get(context + suf))
                if v is not None:
                    return v
            # コンテキストに別の接頭辞が付く版も拾う
            for ctx, val in ctxs.items():
                if ctx.startswith(context):
                    f = to_float(val)
                    if f is not None:
                        return f
        return None

    def series(self, names: str | list[str], *, instant: bool = False) -> list:
        ctxs = INST_CONTEXTS if instant else DUR_CONTEXTS
        return [self.num(names, c) for c in ctxs]

    def text(self, names: str | list[str]) -> str | None:
        if isinstance(names, str):
            names = [names]
        for name in names:
            for val in (self._by_name.get(name) or {}).values():
                if val and val.strip():
                    return val
        return None


def parse_doc(doc_id: str) -> Doc:
    zip_path = ensure_csv_zip(doc_id)
    doc = Doc(doc_id)
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            text = zf.read(name).decode("utf-16", errors="replace")
            for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
                element = (row.get("要素ID") or "").strip()
                context = (row.get("コンテキストID") or "").strip()
                value = (row.get("値") or "").strip()
                if not element or not context or not value:
                    continue
                local = _local(element)
                doc._by_name.setdefault(local, {}).setdefault(context, value)
                if local in META_ELEMENTS:
                    doc.meta.setdefault(META_ELEMENTS[local], value)
    return doc
