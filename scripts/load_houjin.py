"""法人番号公表サイトの CSV(zip) を raw_stage に投入する。

使い方:
    uv run python scripts/load_houjin.py data/raw/31_tottori_all_20261031.zip
    uv run python scripts/load_houjin.py <zip> --city-code 201 --city-code 202
    uv run python scripts/load_houjin.py <差分zip> --pref-code 31
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import zipfile
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg

# ---------------------------------------------------------------------------
# 1. 列定義
# ---------------------------------------------------------------------------
# リソース定義書（ダウンロードファイル）項番 7〜36 の並び順。
COLUMNS = [
    "sequence_number", "corporate_number", "process", "correct", "update_date",
    "change_date", "name", "name_image_id", "kind", "prefecture_name",
    "city_name", "street_number", "address_image_id", "prefecture_code",
    "city_code", "post_code", "address_outside", "address_outside_image_id",
    "close_date", "close_cause", "successor_corporate_number", "change_cause",
    "assignment_date", "latest", "en_name", "en_prefecture_name",
    "en_city_name", "en_address_outside", "furigana", "hihyoji",
]
META_COLUMNS = ["_source_file", "_file_date", "_loaded_at"]

SCHEMA = "raw_stage"
TABLE = "houjin_bangou"
CORPORATE_NUMBER_RE = re.compile(r"^\d{13}$")


# ---------------------------------------------------------------------------
# 2. DB 接続とテーブル作成
# ---------------------------------------------------------------------------
def connect() -> psycopg.Connection:
    missing = [k for k in ("PGDATABASE", "PGUSER", "PGPASSWORD") if k not in os.environ]
    if missing:
        sys.exit(f"環境変数が未設定です: {', '.join(missing)}")
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5433"),
        dbname=os.environ.get("PGDATABASE"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD"),
        autocommit=True,
    )


def ensure_table(conn: psycopg.Connection) -> None:
    source_cols = ",\n   ".join(f"{c} text" for c in COLUMNS)
    conn.execute(f"create schema if not exists {SCHEMA}")
    conn.execute(f"""
        create table if not exists {SCHEMA}.{TABLE} (
            {source_cols},
            _source_file text not null,
            _file_date date not null,
            _loaded_at timestamptz not null
        )
    """)


# ---------------------------------------------------------------------------
# 3. zip から CSV を読む
# ---------------------------------------------------------------------------
def parse_file_date(path: Path, override: str | None) -> date:
    if override:
        return date.fromisoformat(override)
    m = re.search(r"(\d{8})", path.name)
    if not m:
        sys.exit(r"ファイル名から日付を取れません: {path.name} (--file-date で指摘してください)")
    return datetime.strptime(m.group(1), "%Y%m%d").date()


def read_rows(path: Path) -> Iterator[list[str]]:
    with zipfile.ZipFile(path) as zf:
        members = sorted(n for n in zf.namelist() if n.lower().endswith(".csv"))
        if not members:
            sys.exit(f"zip 内に CSV がありません: {path.name}")
        for member in members: # 300MB 超は分割されるため全 CSV を順に読む
            with zf.open(member) as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                for lineno, row in enumerate(csv.reader(text), start=1):
                    if lineno == 1 and not CORPORATE_NUMBER_RE.match(row[1] if len(row) > 1 else ""):
                        continue # ヘッダー行があれば読み飛ばす
                    if len(row) != len(COLUMNS):
                        sys.exit(f"{member}:{lineno} 列数が {len(row)} (期待値 {len(COLUMNS)})")
                    yield row


# ---------------------------------------------------------------------------
# 4. 絞り込み
# ---------------------------------------------------------------------------
def filter_rows(
        rows: Iterator[list[str]], pref_code: str | None, city_codes: set[str]
) -> Iterator[list[str]]:
    i_pref = COLUMNS.index("prefecture_code")
    i_city = COLUMNS.index("city_code")
    for row in rows:
        if pref_code and row[i_pref] != pref_code:
            continue
        if city_codes and row[i_city] not in city_codes:
            continue
        yield row


# ---------------------------------------------------------------------------
# 5. 投入（同じファイルは入れ直す＝冪等）
# ---------------------------------------------------------------------------
def load(conn: psycopg.Connection, rows: Iterator[list[str]], source_file: str, file_date: date) -> tuple[int, int]:
    loaded_at = datetime.now(timezone.utc)
    cols = ", ".join(COLUMNS + META_COLUMNS)
    inserted = 0
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(f"delete from {SCHEMA}.{TABLE} where _source_file = %s", (source_file,))
            deleted = cur.rowcount
            with cur.copy(f"copy {SCHEMA}.{TABLE} ({cols}) from stdin") as copy:
                for row in rows:
                    copy.write_row([*row, source_file, file_date, loaded_at])
                    inserted += 1
    return deleted, inserted


def summarize(conn: psycopg.Connection, source_file: str) -> None:
    rows = conn.execute(
        f"select process, count(*) from {SCHEMA}.{TABLE} "
        f"where _source_file = %s group by process order by process",
        (source_file,),
    ).fetchall()
    print("処理区分別の件数:")
    for process, n in rows:
        print(f" {process}: {n}")


# ---------------------------------------------------------------------------
# 6. エントリポイント
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--pref-code", help="都道府県コード2桁（例: 31）")
    parser.add_argument("--city-code", action="append", default=[], help="市区町村コード3桁。複数指定可")
    parser.add_argument("--file-date", help="ファイル日付 YYYY-MM-DD（ファイル名から取れない場合）")
    args = parser.parse_args()

    if not args.zip_path.exists():
        sys.exit(f"ファイルがありません: {args.zip_path}")

    file_date = parse_file_date(args.zip_path, args.file_date)
    source_file = args.zip_path.name

    with connect() as conn:
        ensure_table(conn)
        rows = filter_rows(read_rows(args.zip_path), args.pref_code, set(args.city_code))
        try:
            deleted, inserted = load(conn, rows, source_file, file_date)
        except UnicodeDecodeError:
            sys.exit("UTF-8 で読めません。CSV「Unicode」版の zip か確認してください")
        print(f"{source_file} (file_date={file_date}): 削除 {deleted} 件 → 投入 {inserted} 件")
        summarize(conn, source_file)

if __name__ == "__main__":
    main()

