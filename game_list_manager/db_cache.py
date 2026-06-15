import os
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path


NON_GROUPABLE_FIELDS = {
    "db_id",
    "game_id",
    "path",
    "rom_stem",
    "base_key",
    "base_stem",
    "is_base_version",
    "release_sort",
    "name",
    "desc",
    "image",
    "video",
    "thumbnail",
    "marquee",
    "fanart",
    "manual",
    "music",
}

TECHNICAL_COLUMNS = {
    "db_id",
    "game_id",
    "path",
    "rom_stem",
    "base_key",
    "base_stem",
    "is_base_version",
    "year",
    "release_sort",
    "catver_category",
    "catver_version",
    "catlist_group",
    "genre_mame",
    "genre_ows",
    "mature_flag",
}

FIELD_LABELS = {
    "system": "Платформа",
    "year": "Год",
    "genre": "Жанр XML",
    "genre_mame": "Жанр MAME",
    "catver_category": "Категория MAME",
    "catlist_group": "Тип машины",
    "developer": "Разработчик",
    "publisher": "Издатель",
    "players": "Игроки",
    "mature_flag": "Mature",
    "cloneof": "Базовая версия",
    "base_key": "Семейство версии",
    "releasedate": "Дата релиза",
    "rating": "Рейтинг",
}


def normalize_rom_stem(path_value):
    path_value = (path_value or "").strip()
    if not path_value:
        return ""
    return Path(path_value).stem.lower()


def normalize_base_key(path_value, cloneof_value):
    cloneof_value = (cloneof_value or "").strip()
    return cloneof_value if cloneof_value else path_value


def normalize_year(releasedate_value):
    releasedate_value = (releasedate_value or "").strip()
    if len(releasedate_value) >= 4 and releasedate_value[:4].isdigit():
        return releasedate_value[:4]
    return ""


def normalize_release_sort(releasedate_value):
    releasedate_value = (releasedate_value or "").strip()
    digits = "".join(ch for ch in releasedate_value if ch.isdigit())
    if not digits:
        return 0
    return int(digits)


def _parse_ini_key_value_sections(file_path):
    data = {}
    current_section = None
    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                continue
            if "=" not in line or current_section is None:
                continue
            key, value = line.split("=", 1)
            data.setdefault(current_section, {})[key.strip().lower()] = value.strip()
    return data


def _parse_ini_section_members(file_path):
    data = {}
    current_section = None
    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                continue
            if current_section is None:
                continue
            data[line.lower()] = current_section
    return data


def _parse_not_mature(file_path):
    values = set()
    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                continue
            values.add(line.lower())
    return values


def load_support_metadata(support_root):
    catver_path = os.path.join(support_root, "catver.ini")
    ui_root = os.path.join(support_root, "UI_files")
    catlist_path = os.path.join(ui_root, "catlist.ini")
    genre_path = os.path.join(ui_root, "genre.ini")
    genre_ows_path = os.path.join(ui_root, "genre_ows.ini")
    not_mature_path = os.path.join(ui_root, "not_mature.ini")

    catver_sections = _parse_ini_key_value_sections(catver_path)
    return {
        "catver_category": catver_sections.get("Category", {}),
        "catver_version": catver_sections.get("VerAdded", {}),
        "catlist_group": _parse_ini_section_members(catlist_path) if os.path.exists(catlist_path) else {},
        "genre_mame": _parse_ini_section_members(genre_path) if os.path.exists(genre_path) else {},
        "genre_ows": _parse_ini_section_members(genre_ows_path) if os.path.exists(genre_ows_path) else {},
        "not_mature": _parse_not_mature(not_mature_path) if os.path.exists(not_mature_path) else set(),
    }


def _quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def _collect_xml_tag_names(curated_xml_path):
    tag_names = set()
    tree = ET.parse(curated_xml_path)
    root = tree.getroot()
    for game_elem in root.findall("game"):
        for child in game_elem:
            tag_names.add(child.tag)
    return sorted(tag_names)


def _create_schema(conn, xml_fields):
    conn.execute("DROP TABLE IF EXISTS games")
    conn.execute("DROP TABLE IF EXISTS metadata")

    column_defs = [
        '"db_id" INTEGER PRIMARY KEY AUTOINCREMENT',
        '"game_id" TEXT',
        '"path" TEXT NOT NULL UNIQUE',
        '"rom_stem" TEXT',
        '"base_key" TEXT',
        '"base_stem" TEXT',
        '"is_base_version" INTEGER',
        '"year" TEXT',
        '"release_sort" INTEGER',
        '"catver_category" TEXT',
        '"catver_version" TEXT',
        '"catlist_group" TEXT',
        '"genre_mame" TEXT',
        '"genre_ows" TEXT',
        '"mature_flag" INTEGER',
    ]

    for field in xml_fields:
        if field in TECHNICAL_COLUMNS:
            continue
        column_defs.append(f'{_quote_identifier(field)} TEXT')

    create_sql = "CREATE TABLE games (\n  " + ",\n  ".join(column_defs) + "\n)"
    conn.execute(create_sql)
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO metadata(key, value) VALUES(?, ?)",
        [(field, "1") for field in xml_fields],
    )
    conn.execute("CREATE INDEX idx_games_base_key ON games(base_key)")
    conn.execute("CREATE INDEX idx_games_path ON games(path)")
    conn.execute("CREATE INDEX idx_games_rom_stem ON games(rom_stem)")
    conn.execute("CREATE INDEX idx_games_year ON games(year)")
    available_columns = TECHNICAL_COLUMNS | set(xml_fields)
    if "system" in available_columns:
        conn.execute("CREATE INDEX idx_games_system ON games(system)")
    if "cloneof" in available_columns:
        conn.execute("CREATE INDEX idx_games_cloneof ON games(cloneof)")


def rebuild_cache(curated_xml_path, db_path, support_root):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    xml_fields = _collect_xml_tag_names(curated_xml_path)
    support = load_support_metadata(support_root)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA temp_store=MEMORY")
        _create_schema(conn, xml_fields)
        tree = ET.parse(curated_xml_path)
        root = tree.getroot()

        xml_insert_fields = [field for field in xml_fields if field not in TECHNICAL_COLUMNS]
        insert_columns = [
            "game_id", "path", "rom_stem", "base_key", "base_stem",
            "is_base_version", "year", "release_sort", "catver_category",
            "catver_version", "catlist_group", "genre_mame", "genre_ows",
            "mature_flag",
        ] + xml_insert_fields

        placeholders = ", ".join("?" for _ in insert_columns)
        quoted_columns = ", ".join(_quote_identifier(col) for col in insert_columns)
        insert_sql = f"INSERT INTO games ({quoted_columns}) VALUES ({placeholders})"

        rows = []
        for game_elem in root.findall("game"):
            values = {field: "" for field in xml_fields}
            for child in game_elem:
                values[child.tag] = child.text or ""

            path_value = values.get("path", "")
            cloneof_value = values.get("cloneof", "")
            rom_stem = normalize_rom_stem(path_value)
            base_key = normalize_base_key(path_value, cloneof_value)
            base_stem = normalize_rom_stem(base_key)
            year_value = normalize_year(values.get("releasedate", ""))
            release_sort = normalize_release_sort(values.get("releasedate", ""))

            row = [
                game_elem.get("id", ""),
                path_value,
                rom_stem,
                base_key,
                base_stem,
                1 if not cloneof_value else 0,
                year_value,
                release_sort,
                support["catver_category"].get(rom_stem, ""),
                support["catver_version"].get(rom_stem, ""),
                support["catlist_group"].get(rom_stem, ""),
                support["genre_mame"].get(rom_stem, ""),
                support["genre_ows"].get(rom_stem, ""),
                0 if rom_stem in support["not_mature"] else 1,
            ]
            row.extend(values.get(field, "") for field in xml_insert_fields)
            rows.append(row)

        conn.executemany(insert_sql, rows)
        conn.commit()
    finally:
        conn.close()


def cache_exists(db_path):
    return os.path.exists(db_path)


def ensure_cache(curated_xml_path, db_path, support_root):
    if not cache_exists(db_path):
        rebuild_cache(curated_xml_path, db_path, support_root)


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_columns(db_path):
    conn = get_connection(db_path)
    try:
        rows = conn.execute("PRAGMA table_info(games)").fetchall()
        return [row["name"] for row in rows]
    finally:
        conn.close()


def get_groupable_fields(db_path):
    columns = get_all_columns(db_path)
    fields = [col for col in columns if col not in NON_GROUPABLE_FIELDS]
    return fields


def get_field_label(field_name):
    return FIELD_LABELS.get(field_name, field_name)


def _validate_order_fields(db_path, field_names):
    available = set(get_all_columns(db_path))
    return [field for field in field_names if field in available]


def load_tree_rows(db_path, grouping_fields):
    order_fields = _validate_order_fields(db_path, grouping_fields)
    order_clause_parts = []
    for field in order_fields:
        order_clause_parts.append(f"COALESCE({_quote_identifier(field)}, '') COLLATE NOCASE")
    order_clause_parts.extend([
        "COALESCE(base_key, '') COLLATE NOCASE",
        "release_sort DESC",
        "is_base_version DESC",
        "COALESCE(name, '') COLLATE NOCASE",
    ])
    order_clause = ", ".join(order_clause_parts)

    conn = get_connection(db_path)
    try:
        rows = conn.execute(f"SELECT * FROM games ORDER BY {order_clause}").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_game_details(db_path, db_id):
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM games WHERE db_id = ?", (db_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_version_candidates(db_path, base_key):
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM games
            WHERE base_key = ?
            ORDER BY release_sort DESC, is_base_version DESC, COALESCE(name, '') COLLATE NOCASE
            """,
            (base_key,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
