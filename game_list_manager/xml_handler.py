import xml.etree.ElementTree as ET
import os

def load_gamelist(xml_path):
    games = []
    systems = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for game in root.findall('game'):
            game_data = {
                'path': game.find('path').text if game.find('path') is not None else '',
                'name': game.find('name').text if game.find('name') is not None else '',
                'desc': game.find('desc').text if game.find('desc') is not None else '',
                'image': game.find('image').text if game.find('image') is not None else '',
                'video': game.find('video').text if game.find('video') is not None else '',
                'rating': game.find('rating').text if game.find('rating') is not None else '0',
                'releasedate': game.find('releasedate').text if game.find('releasedate') is not None else '',
                'genre': game.find('genre').text if game.find('genre') is not None else 'Unknown',
                'players': game.find('players').text if game.find('players') is not None else '1',
                'cloneof': game.find('cloneof').text if game.find('cloneof') is not None else ''
            }
            system = game.find('system').text if game.find('system') is not None else 'Unknown'
            games.append(game_data)
            if system not in systems:
                systems[system] = []
            systems[system].append(game_data)
        print(f"Loaded gamelist from {xml_path}")
        return games, systems
    except Exception as e:
        print(f"Error loading gamelist: {e}")
        return [], {}

def save_xml(games, xml_path):
    try:
        root = ET.Element("gameList")
        for game in games:
            game_elem = ET.SubElement(root, "game")
            for key, value in game.items():
                if key == 'iid':
                    continue
                elem = ET.SubElement(game_elem, key)
                elem.text = str(value) if value is not None else ''
        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        print(f"Saved gamelist to {xml_path}")
    except Exception as e:
        print(f"Error saving gamelist: {e}")