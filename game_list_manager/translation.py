import time
import threading
import shutil
from googletrans import Translator
from tkinter import ttk, messagebox
from xml_handler import save_xml
import xml.etree.ElementTree as ET
import os

def needs_translation(text):
    if not text or not text.strip():
        return False
    cyrillic_chars = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
    has_cyrillic = any(char.lower() in cyrillic_chars for char in text)
    return not has_cyrillic

def translate_text(text, retries=3, delay=1):
    translator = Translator()
    for _ in range(retries):
        try:
            return translator.translate(text, src='en', dest='ru').text
        except Exception:
            time.sleep(delay)
    return text

def translate_all(app):
    if not app.games:
        messagebox.showinfo("Info", "Нет игр для перевода")
        return

    xml_path = os.path.join(app.rom_dir, 'gamelist.xml')
    backup_xml(xml_path)
    app.progress["value"] = 0

    stats_frame = ttk.Frame(app.root)
    stats_frame.pack(fill=tk.X, padx=10, pady=5)
    
    eta_label = ttk.Label(stats_frame, text="ETA: --:--:--")
    eta_label.pack(side=tk.LEFT, padx=5)
    
    speed_label = ttk.Label(stats_frame, text="Скорость: 0/сек")
    speed_label.pack(side=tk.LEFT, padx=5)
    
    remaining_label = ttk.Label(stats_frame, text="Осталось: 0")
    remaining_label.pack(side=tk.LEFT, padx=5)

    def worker():
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        xml_elements_by_id = {}
        for game_elem in root.findall('game'):
            game_id = game_elem.get('id')
            if game_id:
                xml_elements_by_id[game_id] = game_elem
        
        games_to_translate = []
        for game in app.games:
            if game['desc'] and needs_translation(game['desc']):
                games_to_translate.append(game)
        
        total_to_translate = len(games_to_translate)
        app.progress["maximum"] = total_to_translate
        
        if not games_to_translate:
            messagebox.showinfo("Info", "Все описания уже переведены или пустые")
            stats_frame.destroy()
            return

        start_time = time.time()
        translated_count = 0
        last_update_time = start_time
        last_translated_count = 0
        
        def update_stats(current_count):
            nonlocal last_update_time, last_translated_count
            
            current_time = time.time()
            time_diff = current_time - last_update_time
            count_diff = current_count - last_translated_count
            
            if time_diff > 30:
                last_update_time = current_time
                last_translated_count = current_count
                time_diff = 30
            
            if time_diff > 0:
                speed = count_diff / time_diff
            else:
                speed = 0
            
            speed_label.config(text=f"Скорость: {speed:.2f}/сек")
            
            remaining = total_to_translate - current_count
            remaining_label.config(text=f"Осталось: {remaining}")
            
            if speed > 0 and remaining > 0:
                eta_seconds = remaining / speed
                hours = int(eta_seconds // 3600)
                minutes = int((eta_seconds % 3600) // 60)
                seconds = int(eta_seconds % 60)
                eta_label.config(text=f"ETA: {hours:02d}:{minutes:02d}:{seconds:02d}")
            else:
                eta_label.config(text="ETA: --:--:--")
            
            app.progress["value"] = current_count
            app.root.update_idletasks()

        def save_progress():
            tree.write(xml_path, encoding='utf-8', xml_declaration=True)

        batches = []
        current_batch = []
        current_chars = 0
        max_chars = 5000

        for game in games_to_translate:
            text_length = len(game['desc'])
            if current_chars + text_length < max_chars and len(current_batch) < 10:
                current_batch.append(game)
                current_chars += text_length
            else:
                batches.append(current_batch)
                current_batch = [game]
                current_chars = text_length
        
        if current_batch:
            batches.append(current_batch)

        save_interval = 50
        
        for i, batch in enumerate(batches):
            try:
                batch_texts = []
                for game in batch:
                    batch_texts.append(f"---{game['id']}---")
                    batch_texts.append(game['desc'])
                
                combined_text = "\n".join(batch_texts)
                
                translated = translate_text(combined_text)
                
                translated_parts = {}
                current_id = None
                current_text = []
                
                for line in translated.split('\n'):
                    line = line.strip()
                    if line.startswith('---') and line.endswith('---'):
                        if current_id is not None and current_text:
                            translated_parts[current_id] = '\n'.join(current_text).strip()
                        
                        current_id = line.strip('-').strip()
                        current_text = []
                    elif current_id is not None and line:
                        current_text.append(line)
                
                if current_id is not None and current_text:
                    translated_parts[current_id] = '\n'.join(current_text).strip()
                
                for game in batch:
                    game_id = game['id']
                    found_id = None
                    for key in translated_parts.keys():
                        if key.strip() == game_id:
                            found_id = key
                            break
                    
                    if found_id:
                        translated_text = translated_parts[found_id]
                        game['desc'] = translated_text
                        xml_elem = xml_elements_by_id.get(game_id)
                        if xml_elem is not None:
                            desc_elem = xml_elem.find("desc")
                            if desc_elem is not None:
                                desc_elem.text = translated_text
                            else:
                                new_desc = ET.SubElement(xml_elem, "desc")
                                new_desc.text = translated_text
                
                translated_count += len(batch)
                update_stats(translated_count)
                
                if (i + 1) % save_interval == 0:
                    save_progress()
                
                if i < len(batches) - 1:
                    time.sleep(0.5)
                    
            except Exception:
                for game in batch:
                    try:
                        translated = translate_text(game['desc'])
                        game['desc'] = translated
                        xml_elem = xml_elements_by_id.get(game['id'])
                        if xml_elem is not None:
                            desc_elem = xml_elem.find("desc")
                            if desc_elem is not None:
                                desc_elem.text = translated
                            else:
                                new_desc = ET.SubElement(xml_elem, "desc")
                                new_desc.text = translated
                        
                        translated_count += 1
                        update_stats(translated_count)
                        time.sleep(1)
                    except Exception:
                        translated_count += 1
                        update_stats(translated_count)
                
                save_progress()

        save_progress()
        stats_frame.destroy()
        
        from xml_handler import parse_xml, group_by_system
        app.games = parse_xml(app.rom_dir)
        app.systems = group_by_system(app.games)
        app.populate_tree()
        
        messagebox.showinfo("Готово", f"Переведено {translated_count} из {total_to_translate} описаний")

    threading.Thread(target=worker, daemon=True).start()

def backup_xml(xml_path):
    base, ext = os.path.splitext(xml_path)
    i = 0
    while True:
        bak = f"{base}.bak{i}" if i else f"{base}.bak"
        if not os.path.exists(bak):
            shutil.copy(xml_path, bak)
            break
        i += 1
