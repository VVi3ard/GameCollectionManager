import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


CURATED_XML_FILENAME = "curated_gamelist.xml"
PROJECT_STATE_FILENAME = "project_state.json"
CACHE_DB_FILENAME = "curated_cache.sqlite"
FILE_REFERENCE_TAGS = {
    'path',
    'image',
    'video',
    'thumbnail',
    'marquee',
    'fanart',
    'boxart',
    'titleshot',
    'screenshot',
    'manual',
    'pdf',
    'music',
}


def prepare_collection_workspace(rom_dir):
    rom_dir = os.path.normpath(rom_dir)
    source_xml_path = os.path.join(rom_dir, 'gamelist.xml')
    checked_dir = os.path.join(rom_dir, 'checked')
    curated_xml_path = os.path.join(checked_dir, CURATED_XML_FILENAME)
    project_state_path = os.path.join(checked_dir, PROJECT_STATE_FILENAME)
    cache_db_path = os.path.join(checked_dir, CACHE_DB_FILENAME)
    support_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pS_CatVer_287")

    os.makedirs(checked_dir, exist_ok=True)

    if not os.path.exists(curated_xml_path):
        shutil.copy2(source_xml_path, curated_xml_path)
        print(f"Created curated XML: {curated_xml_path}")

    return {
        "source_xml_path": source_xml_path,
        "checked_dir": checked_dir,
        "curated_xml_path": curated_xml_path,
        "project_state_path": project_state_path,
        "cache_db_path": cache_db_path,
        "support_root": support_root,
    }


def load_gamelist(xml_path):
    games = []
    systems = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for game in root.findall('game'):
            game_data = {
                'id': game.get('id', ''),
                'path': game.find('path').text if game.find('path') is not None else '',
                'name': game.find('name').text if game.find('name') is not None else '',
                'desc': game.find('desc').text if game.find('desc') is not None else '',
                'image': game.find('image').text if game.find('image') is not None else '',
                'video': game.find('video').text if game.find('video') is not None else '',
                'rating': game.find('rating').text if game.find('rating') is not None else '0',
                'releasedate': game.find('releasedate').text if game.find('releasedate') is not None else '',
                'genre': game.find('genre').text if game.find('genre') is not None else 'Unknown',
                'players': game.find('players').text if game.find('players') is not None else '1',
                'cloneof': game.find('cloneof').text if game.find('cloneof') is not None else '',
                'system': game.find('system').text if game.find('system') is not None else 'Unknown',
            }
            system = game_data['system']
            games.append(game_data)
            systems.setdefault(system, []).append(game_data)
        print(f"Loaded gamelist from {xml_path}")
        return games, systems
    except Exception as e:
        print(f"Error loading gamelist: {e}")
        return [], {}


def parse_xml(xml_path):
    games, _ = load_gamelist(xml_path)
    return games


def group_by_system(games):
    systems = {}
    for game in games:
        system = game.get('system') or 'Unknown'
        systems.setdefault(system, []).append(game)
    return systems


def save_xml(games, xml_path):
    try:
        root = ET.Element("gameList")
        for game in games:
            game_elem = ET.SubElement(root, "game")
            game_id = game.get('id')
            if game_id:
                game_elem.set('id', str(game_id))
            for key, value in game.items():
                if key in {'iid', 'id'}:
                    continue
                elem = ET.SubElement(game_elem, key)
                elem.text = str(value) if value is not None else ''
        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        print(f"Saved gamelist to {xml_path}")
    except Exception as e:
        print(f"Error saving gamelist: {e}")


def looks_like_file_reference(tag_name, value):
    lowered_tag = tag_name.lower()
    lowered_value = value.lower()

    if lowered_tag in FILE_REFERENCE_TAGS:
        return True

    if lowered_value.startswith(('http://', 'https://')):
        return False

    suffix = Path(lowered_value).suffix
    if suffix in {
        '.zip', '.7z', '.chd', '.cue', '.bin', '.iso',
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp',
        '.mp4', '.avi', '.mkv', '.webm', '.flv',
        '.mp3', '.ogg', '.wav', '.flac',
        '.pdf',
    }:
        return True

    return ('/' in value) or ('\\' in value)


def resolve_collection_path(collection_root, relative_path):
    collection_root = Path(collection_root).resolve()
    candidate = (collection_root / relative_path).resolve()

    try:
        candidate.relative_to(collection_root)
    except ValueError:
        print(f"Skipped path outside collection: {candidate}")
        return None

    return candidate


def collect_game_file_paths(game_elem, collection_root):
    file_paths = set()
    for child in game_elem:
        child_text = (child.text or '').strip()
        if not child_text:
            continue

        if not looks_like_file_reference(child.tag, child_text):
            continue

        resolved_path = resolve_collection_path(collection_root, child_text)
        if resolved_path is not None:
            file_paths.add(resolved_path)

    return file_paths


def export_curated_collection(curated_xml_path, source_root, export_root):
    source_root = Path(source_root).resolve()
    export_root = Path(export_root).resolve()

    tree = ET.parse(curated_xml_path)
    root = tree.getroot()

    export_root.mkdir(parents=True, exist_ok=True)

    files_to_copy = set()
    missing_files = []
    for game_elem in root.findall('game'):
        for file_path in collect_game_file_paths(game_elem, source_root):
            if file_path.exists() and file_path.is_file():
                files_to_copy.add(file_path)
            else:
                missing_files.append(str(file_path))

    copied_files = 0
    for source_path in sorted(files_to_copy):
        relative_path = source_path.relative_to(source_root)
        destination_path = export_root / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        copied_files += 1

    export_xml_path = export_root / 'gamelist.xml'
    tree.write(export_xml_path, encoding='utf-8', xml_declaration=True)

    return {
        "games_count": len(root.findall('game')),
        "copied_files": copied_files,
        "missing_files": missing_files,
        "export_xml_path": str(export_xml_path),
    }
