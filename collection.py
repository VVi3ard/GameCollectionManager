import time
import tkinter as tk
from tkinter import ttk, messagebox, Text
import xml.etree.ElementTree as ET
import os
from PIL import Image, ImageTk
import threading
from datetime import datetime
import shutil
from googletrans import Translator
from tkvideo import tkvideo
import subprocess
import json
from pathlib import Path
import concurrent.futures
import queue
import uuid


class GameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Game List Manager")
        self.root.geometry("1200x600")

        # Base directory (where the app is run from)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        # XML file path
        self.xml_path = os.path.join(self.base_dir, 'gamelist.xml')
        
        # Checked items file path
        self.checked_file = os.path.join(self.base_dir, 'checked')

        # Load games
        self.games = self.parse_xml()
        self.systems = self.group_by_system()
        
        # Checked items set (iid of tree items)
        self.checked = set()

        # Current selected game
        self.current_game = None
        self.original_image = None
        self.video_size = (320, 240)

        # Translator
        self.translator = Translator()

        # Video attribute
        self.video_player = None

        # UI setup
        self.setup_ui()
        self.load_checked()

    # ----------------------------- Checked Items Save/Load -----------------------------

    def save_checked(self):
        """Сохраняет отмеченные элементы в файл"""
        try:
            with open(self.checked_file, 'w', encoding='utf-8') as f:
                for iid in self.checked:
                    # Сохраняем iid и имя игры для надежности
                    game = next((g for g in self.games if g.get('iid') == iid), None)
                    if game:
                        f.write(f"{iid}|{game['name']}\n")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить отметки: {e}")

    def load_checked(self):
        """Загружает отмеченные элементы из файла"""
        if not os.path.exists(self.checked_file):
            return
        
        try:
            with open(self.checked_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split('|', 1)
                        if len(parts) >= 1:
                            iid = parts[0]
                            self.checked.add(iid)
            
            # Обновляем визуальное отображение отметок
            self.update_checked_visuals()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить отметки: {e}")

    def update_checked_visuals(self):
        """Обновляет визуальное отображение отмеченных элементов"""
        for game in self.games:
            iid = game.get('iid')
            if iid and iid in self.checked:
                current_text = self.tree.item(iid)['text']
                if '☐' in current_text:
                    self.tree.item(iid, text=current_text.replace('☐', '☑'), tags=('checked',))

    # ----------------------------- XML -----------------------------

    def parse_xml(self):
        if not os.path.exists(self.xml_path):
            messagebox.showerror("Error", "gamelist.xml not found!")
            self.root.quit()
            return []

        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        games = []
        for game in root.findall('game'):
            g = {
                'id': game.get('id'),
                'path': game.findtext('path'),
                'name': game.findtext('name'),
                'desc': game.findtext('desc'),
                'rating': game.findtext('rating'),
                'releasedate': game.findtext('releasedate'),
                'genre': game.findtext('genre'),
                'players': game.findtext('players'),
                'system': game.findtext('system'),
                'image': game.find('image').text if game.find('image') is not None else None,
                'video': game.find('video').text if game.find('video') is not None else None,
                'xml_element': game
            }
            games.append(g)
        return games

    def group_by_system(self):
        systems = {}
        for game in self.games:
            sys = game['system']
            if sys not in systems:
                systems[sys] = []
            systems[sys].append(game)
        return systems

    # ----------------------------- UI -----------------------------

    def setup_ui(self):
        # Paned window for split view
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Treeview for games
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(left_frame, orient="vertical")
        tree_scroll_x = ttk.Scrollbar(left_frame, orient="horizontal")

        self.tree = ttk.Treeview(
            left_frame,
            columns=("name",),
            show="tree",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)

        self.tree.column("#0", width=400, stretch=True)

        # Populate tree
        self.populate_tree()

        # Bindings
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<space>', self.toggle_check)
        self.tree.bind('<Down>', self.on_down)

        # Right: Details
        self.right_frame = ttk.Frame(paned)
        paned.add(self.right_frame, weight=2)

        # Desc text
        self.desc_text = Text(self.right_frame, wrap=tk.WORD, height=10)
        self.desc_text.pack(fill=tk.X, pady=5)

        # Image label
        self.image_label = tk.Label(self.right_frame)
        self.image_label.pack(fill=tk.BOTH, expand=True, pady=5)

        # Video frame
        self.video_frame = ttk.Frame(self.right_frame)
        self.video_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Bind resize
        self.right_frame.bind("<Configure>", self.on_resize)

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10, fill=tk.X)

        delete_btn = ttk.Button(btn_frame, text="Удалить отмеченные", command=self.delete_checked)
        delete_btn.pack(side=tk.LEFT, padx=5)

        translate_btn = ttk.Button(btn_frame, text="Перевести всё", command=self.translate_all)
        translate_btn.pack(side=tk.LEFT, padx=5)

        save_marks_btn = ttk.Button(btn_frame, text="Сохранить отметки", command=self.save_checked)
        save_marks_btn.pack(side=tk.LEFT, padx=5)
        
        load_marks_btn = ttk.Button(btn_frame, text="Загрузить отметки", command=self.load_checked)
        load_marks_btn.pack(side=tk.LEFT, padx=5)

        compress_btn = ttk.Button(btn_frame, text="Сжать видео", command=self.compress_video)
        compress_btn.pack(side=tk.LEFT, padx=5)

        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=5)

    def populate_tree(self):
        for sys in sorted(self.systems.keys()):
            parent = self.tree.insert('', 'end', text=sys, open=True)
            for game in self.systems[sys]:
                year = ''
                if game['releasedate']:
                    try:
                        dt = datetime.strptime(game['releasedate'], '%Y%m%dT%H%M%S')
                        year = dt.year
                    except ValueError:
                        year = game['releasedate'][:4]
                
                # Создаем iid для игры
                label = f"☐ {game['name']} ({game['genre']}, {game['players']} players, rating {game['rating']}, {year})"
                iid = self.tree.insert(parent, 'end', text=label, tags=('unchecked',))
                game['iid'] = iid
        
        # После создания всех элементов обновляем отметки
        self.update_checked_visuals()

    # ----------------------------- Tree Actions -----------------------------

    def toggle_check(self, event):
        selected_items = self.tree.selection()
        
        for item in selected_items:
            if not item or self.tree.parent(item) == '':
                continue
            if item in self.checked:
                self.checked.remove(item)
                self.tree.item(item, text=self.tree.item(item)['text'].replace('☑', '☐'), tags=('unchecked',))
            else:
                self.checked.add(item)
                self.tree.item(item, text=self.tree.item(item)['text'].replace('☐', '☑'), tags=('checked',))
        # Автоматически сохраняем отметки после изменения
        self.save_checked()
        
    def on_down(self, event):
        pass

    def on_select(self, event):
        item = self.tree.focus()
        if not item or self.tree.parent(item) == '':
            return

        try:
            self.current_game = next(g for g in self.games if g.get('iid') == item)
        except StopIteration:
            return

        # Функция проверки на русский язык
        def is_russian(text):
            if not text or not text.strip():
                return False
            cyrillic_chars = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
            russian_count = sum(1 for char in text if char.lower() in cyrillic_chars)
            # Считаем текст русским если более 30% символов - кириллица
            return russian_count / len(text) > 0.3

        # Получаем описание
        desc = self.current_game['desc']
        
        # Проверяем, нужно ли переводить
        if desc and not is_russian(desc):
            try:
                translated = self.translator.translate(desc, src='en', dest='ru').text
                # Показываем переведенное описание
                self.desc_text.delete(1.0, tk.END)
                self.desc_text.insert(tk.END, translated)
            except Exception:
                # Если перевод не удался, показываем оригинал
                self.desc_text.delete(1.0, tk.END)
                self.desc_text.insert(tk.END, desc)
        else:
            # Если уже на русском или пустое, показываем как есть
            self.desc_text.delete(1.0, tk.END)
            self.desc_text.insert(tk.END, desc if desc else "Нет описания")

        # Show image
        if self.current_game['image']:
            img_path = os.path.join(self.base_dir, self.current_game['image'])
            if os.path.exists(img_path):
                self.original_image = Image.open(img_path)
                self.resize_image()
            else:
                self.image_label.config(image=None, text="Image not found")
        else:
            self.image_label.config(image=None, text="No image")

        # Play video
        self.stop_video()
        if self.current_game['video']:
            video_path = os.path.join(self.base_dir, self.current_game['video'])
            if os.path.exists(video_path):
                self.play_video(video_path)
            else:
                label = tk.Label(self.video_frame, text="Video not found")
                label.pack()
        else:
            label = tk.Label(self.video_frame, text="No video")
            label.pack()

    # ----------------------------- Resizing -----------------------------

    def on_resize(self, event):
        width = self.right_frame.winfo_width()
        height = (self.right_frame.winfo_height() - self.desc_text.winfo_height() - 20) // 2
        self.video_size = (width, height)
        self.resize_image()

    def resize_image(self):
        if self.original_image:
            width = self.right_frame.winfo_width()
            height = (self.right_frame.winfo_height() - self.desc_text.winfo_height() - 20) // 2
            orig_w, orig_h = self.original_image.size
            ratio = min(width / orig_w, height / orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            resized = self.original_image.resize((new_w, new_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            self.image_label.config(image=photo)
            self.image_label.image = photo

    # ----------------------------- Video -----------------------------

    def play_video(self, path):
        try:
            for widget in self.video_frame.winfo_children():
                widget.destroy()
                
            video_label = tk.Label(self.video_frame)
            video_label.pack(expand=True, fill="both")
            
            player = tkvideo(path, video_label, loop=0, size=self.video_size)
            player.play()
            
        except Exception:
            label = tk.Label(self.video_frame, text="Ошибка воспроизведения видео")
            label.pack()

    def stop_video(self):
        for widget in self.video_frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass

    # ----------------------------- Delete -----------------------------

    def delete_checked(self):
        if not self.checked:
            messagebox.showinfo("Info", "No items checked")
            return

        self.backup_xml()
        
        # Загружаем актуальное XML дерево
        tree = ET.parse(self.xml_path)
        root = tree.getroot()
        
        # Создаем mapping для быстрого доступа к XML элементам
        xml_elements_by_id = {}
        for game_elem in root.findall('game'):
            game_id = game_elem.get('id')
            if game_id:
                xml_elements_by_id[game_id] = game_elem

        games_to_remove = []
        for iid in list(self.checked):
            # Находим игру по iid
            game_to_remove = None
            for game in self.games:
                if game.get('iid') == iid:
                    game_to_remove = game
                    break
            
            if game_to_remove:
                # Удаляем из XML дерева
                xml_elem = xml_elements_by_id.get(game_to_remove['id'])
                if xml_elem is not None:
                    root.remove(xml_elem)
                
                # Удаляем файлы
                self.delete_file(game_to_remove['path'])
                self.delete_file(game_to_remove['image'])
                self.delete_file(game_to_remove['video'])
                
                # Удаляем из дерева
                self.tree.delete(iid)
                
                # Помечаем для удаления из списка игр
                games_to_remove.append(game_to_remove)

        # Удаляем игры из списка
        for game in games_to_remove:
            self.games.remove(game)

        # Сохраняем изменения в XML файл
        tree.write(self.xml_path, encoding='utf-8', xml_declaration=True)
        self.checked.clear()
        self.save_checked()
        messagebox.showinfo("Success", "Checked items deleted")
    
    def backup_xml(self):
        base, ext = os.path.splitext(self.xml_path)
        i = 0
        while True:
            bak = f"{base}.bak{i}" if i else f"{base}.bak"
            if not os.path.exists(bak):
                shutil.copy(self.xml_path, bak)
                break
            i += 1

    def delete_file(self, rel_path):
        if rel_path:
            full_path = os.path.join(self.base_dir, rel_path)
            if os.path.exists(full_path):
                os.remove(full_path)

    # ----------------------------- Translation -----------------------------

    def translate_all(self):
        if not self.games:
            messagebox.showinfo("Info", "Нет игр для перевода")
            return

        self.backup_xml()
        self.progress["value"] = 0

        # Create statistics labels
        stats_frame = ttk.Frame(self.root)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.eta_label = ttk.Label(stats_frame, text="ETA: --:--:--")
        self.eta_label.pack(side=tk.LEFT, padx=5)
        
        self.speed_label = ttk.Label(stats_frame, text="Скорость: 0/сек")
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        self.remaining_label = ttk.Label(stats_frame, text="Осталось: 0")
        self.remaining_label.pack(side=tk.LEFT, padx=5)

        def needs_translation(text):
            if not text or not text.strip():
                return False
            cyrillic_chars = set('абвгдеёжзийклмнопрстуфхцчшщъыьэюя')
            has_cyrillic = any(char.lower() in cyrillic_chars for char in text)
            return not has_cyrillic

        def worker():
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            
            xml_elements_by_id = {}
            for game_elem in root.findall('game'):
                game_id = game_elem.get('id')
                if game_id:
                    xml_elements_by_id[game_id] = game_elem
            
            games_to_translate = []
            for game in self.games:
                if game['desc'] and needs_translation(game['desc']):
                    games_to_translate.append(game)
            
            total_to_translate = len(games_to_translate)
            self.progress["maximum"] = total_to_translate
            
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
                
                self.speed_label.config(text=f"Скорость: {speed:.2f}/сек")
                
                remaining = total_to_translate - current_count
                self.remaining_label.config(text=f"Осталось: {remaining}")
                
                if speed > 0 and remaining > 0:
                    eta_seconds = remaining / speed
                    hours = int(eta_seconds // 3600)
                    minutes = int((eta_seconds % 3600) // 60)
                    seconds = int(eta_seconds % 60)
                    self.eta_label.config(text=f"ETA: {hours:02d}:{minutes:02d}:{seconds:02d}")
                else:
                    self.eta_label.config(text="ETA: --:--:--")
                
                self.progress["value"] = current_count
                self.root.update_idletasks()

            def translate_with_retry(text, max_retries=3):
                for attempt in range(max_retries):
                    try:
                        translated = self.translator.translate(text, src='en', dest='ru').text
                        return translated
                    except Exception:
                        if attempt == max_retries - 1:
                            raise
                        time.sleep(2)
                return text

            def save_progress():
                try:
                    tree.write(self.xml_path, encoding='utf-8', xml_declaration=True)
                except Exception:
                    pass

            # Batch translation with ID separators
            batches = []
            current_batch = []
            current_chars = 0
            
            for game in games_to_translate:
                text_length = len(game['desc'])
                
                if not current_batch or (current_chars + text_length < 4000 and len(current_batch) < 10):
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
                    # Create batch with ID separators
                    batch_texts = []
                    for game in batch:
                        batch_texts.append(f"---{game['id']}---")
                        batch_texts.append(game['desc'])
                    
                    combined_text = "\n".join(batch_texts)
                    
                    # Translate the whole batch
                    translated = translate_with_retry(combined_text)
                    
                    # Parse the result by ID separators
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
                    
                    # Update games based on ID
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
                    # Individual translation as fallback
                    for game in batch:
                        try:
                            translated = translate_with_retry(game['desc'])
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
            
            self.games = self.parse_xml()
            self.systems = self.group_by_system()
            
            messagebox.showinfo("Готово", f"Переведено {translated_count} из {total_to_translate} описаний")

        threading.Thread(target=worker, daemon=True).start()

    # ----------------------------- Video Compression -----------------------------

    def compress_video(self):
        """Массовое сжатие видеофайлов - работа напрямую с файлами"""
        # Создаем диалог выбора опций
        compression_dialog = tk.Toplevel(self.root)
        compression_dialog.title("Настройки сжатия видео")
        compression_dialog.geometry("500x450")
        
        ttk.Label(compression_dialog, text="Настройки сжатия видео", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Переменные для настроек
        scale_var = tk.DoubleVar(value=0.75)
        crf_var = tk.IntVar(value=27)
        max_duration_var = tk.IntVar(value=10)
        parallel_var = tk.IntVar(value=6)
        
        # Фрейм настроек
        settings_frame = ttk.Frame(compression_dialog)
        settings_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Настройки сжатия
        ttk.Label(settings_frame, text="Масштаб (0.1-1.0):").grid(row=0, column=0, sticky=tk.W, pady=5)
        scale_scale = ttk.Scale(settings_frame, from_=0.1, to=1.0, variable=scale_var, orient=tk.HORIZONTAL)
        scale_scale.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        ttk.Label(settings_frame, textvariable=scale_var).grid(row=0, column=2, padx=5)
        
        ttk.Label(settings_frame, text="Качество (CRF 0-51):").grid(row=1, column=0, sticky=tk.W, pady=5)
        crf_scale = ttk.Scale(settings_frame, from_=0, to=51, variable=crf_var, orient=tk.HORIZONTAL)
        crf_scale.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        ttk.Label(settings_frame, textvariable=crf_var).grid(row=1, column=2, padx=5)
        
        # Пояснение качества
        crf_info_text = tk.StringVar()
        crf_info_text.set("27 - хорошее качество (по умолчанию)")
        
        def update_crf_info(*args):
            crf_value = crf_var.get()
            if crf_value <= 18:
                crf_info_text.set("18-23 - отличное качество")
            elif crf_value <= 27:
                crf_info_text.set("23-27 - хорошее качество")
            elif crf_value <= 35:
                crf_info_text.set("28-35 - среднее качество")
            else:
                crf_info_text.set("36-51 - низкое качество")
        
        crf_var.trace('w', update_crf_info)
        ttk.Label(settings_frame, textvariable=crf_info_text, font=("Arial", 8)).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        ttk.Label(settings_frame, text="Макс. длительность (сек):").grid(row=3, column=0, sticky=tk.W, pady=5)
        duration_spin = ttk.Spinbox(settings_frame, from_=5, to=60, textvariable=max_duration_var, width=10)
        duration_spin.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        
        # Настройки параллелизма
        ttk.Label(settings_frame, text="Параллельных задач:").grid(row=4, column=0, sticky=tk.W, pady=5)
        parallel_spin = ttk.Spinbox(settings_frame, from_=1, to=12, textvariable=parallel_var, width=10)
        parallel_spin.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)
        
        settings_frame.columnconfigure(1, weight=1)
        
        # Статус
        status_var = tk.StringVar(value="Готов к обработке")
        status_label = ttk.Label(compression_dialog, textvariable=status_var)
        status_label.pack(pady=10)
        
        progress = ttk.Progressbar(compression_dialog, mode="determinate")
        progress.pack(fill=tk.X, padx=20, pady=5)
        
        # Статус параллельных задач
        parallel_frame = ttk.Frame(compression_dialog)
        parallel_frame.pack(fill=tk.X, padx=20, pady=5)
        
        ttk.Label(parallel_frame, text="Активные задачи:").pack(anchor=tk.W)
        active_tasks_var = tk.StringVar(value="0/0")
        active_label = ttk.Label(parallel_frame, textvariable=active_tasks_var)
        active_label.pack(anchor=tk.W)
        
        def start_compression():
            # ПОЛУЧАЕМ ВСЕ MP4 ФАЙЛЫ НАПРЯМУЮ ИЗ ПАПКИ, ИСКЛЮЧАЯ BACKUP
            video_files = []
            media_dir = os.path.join(self.base_dir, "media")
            
            # Ищем все mp4 файлы в папках media, исключая backup
            for root, dirs, files in os.walk(media_dir):
                # Исключаем папку backup из поиска
                if 'backup' in dirs:
                    dirs.remove('backup')
                
                for file in files:
                    if file.lower().endswith('.mp4'):
                        full_path = os.path.join(root, file)
                        video_files.append((file, full_path))
            
            if not video_files:
                status_var.set("MP4 файлы не найдены в media/")
                return
            
            total_files = len(video_files)
            progress["maximum"] = total_files
            progress["value"] = 0
            
            max_workers = parallel_var.get()
            
            def compress_worker():
                completed_count = 0
                task_queue = queue.Queue()
                
                for video_file in video_files:
                    task_queue.put(video_file)
                
                def worker_task(file_info):
                    filename, full_path = file_info
                    try:
                        status_var.set(f"Обработка: {filename}")
                        result = self.compress_video_file(
                            full_path, 
                            scale_var.get(),
                            crf_var.get(),
                            max_duration_var.get()
                        )
                        return (filename, result, None)
                    except Exception as e:
                        return (filename, False, str(e))
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    active_tasks = 0
                    
                    def update_status():
                        active_tasks_var.set(f"{active_tasks}/{max_workers}")
                        compression_dialog.update_idletasks()
                    
                    # Запускаем первоначальные задачи
                    for _ in range(min(max_workers, task_queue.qsize())):
                        if not task_queue.empty():
                            file_info = task_queue.get()
                            future = executor.submit(worker_task, file_info)
                            futures[future] = file_info
                            active_tasks += 1
                            update_status()
                    
                    # Обрабатываем завершенные задачи
                    while futures:
                        done, _ = concurrent.futures.wait(futures.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
                        
                        for future in done:
                            file_info = futures.pop(future)
                            filename, success, error = future.result()
                            
                            completed_count += 1
                            progress["value"] = completed_count
                            
                            if error:
                                print(f"Ошибка сжатия {filename}: {error}")
                            else:
                                print(f"Успешно: {filename}")
                            
                            # Запускаем новую задачу если есть в очереди
                            if not task_queue.empty():
                                new_file_info = task_queue.get()
                                new_future = executor.submit(worker_task, new_file_info)
                                futures[new_future] = new_file_info
                            else:
                                active_tasks -= 1
                            
                            update_status()
                            compression_dialog.update_idletasks()
                    
                status_var.set("Обработка завершена!")
                messagebox.showinfo("Готово", f"Сжатие видео завершено\nОбработано: {completed_count}/{total_files}")
            
            threading.Thread(target=compress_worker, daemon=True).start()
        
        # Кнопки
        btn_frame = ttk.Frame(compression_dialog)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Начать сжатие", command=start_compression).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=compression_dialog.destroy).pack(side=tk.LEFT, padx=5)

    def compress_video_file(self, input_path, scale_factor, crf_value, max_duration):
        """Сжатие видеофайла без привязки к XML"""
        try:
            input_path = os.path.normpath(input_path)
            
            # ЗАЩИТА ОТ ОБРАБОТКИ ФАЙЛОВ В BACKUP
            if 'backup' in input_path.split(os.sep):
                raise Exception("Попытка обработки файла в папке backup")
            
            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Файл не существует: {input_path}")
            
            print(f"Сжатие: {os.path.basename(input_path)}")
            
            # Создаем папку backup рядом с файлом
            file_dir = os.path.dirname(input_path)
            backup_dir = os.path.join(file_dir, "backup")
            os.makedirs(backup_dir, exist_ok=True)
            
            filename = os.path.basename(input_path)
            backup_path = os.path.join(backup_dir, filename)
            
            # Backup файла (только если еще не существует)
            if not os.path.exists(backup_path):
                shutil.copy2(input_path, backup_path)
                print(f"Создан backup: {backup_path}")
            else:
                print(f"Используем существующий backup")
            
            # Уникальное временное имя
            temp_id = uuid.uuid4().hex[:8]
            output_path = f"{input_path}.{temp_id}.temp.mp4"
            output_path = os.path.normpath(output_path)
            
            # Получаем информацию о видео
            cmd_info = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", input_path
            ]
            
            result = subprocess.run(cmd_info, capture_output=True, text=True)
            
            if result.returncode != 0:
                duration = 10.0
                width, height = 640, 480
                print("Используем значения по умолчанию")
            else:
                info = json.loads(result.stdout)
                video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
                if not video_stream:
                    raise Exception("Видео поток не найден")
                
                duration = float(info['format']['duration'])
                width = int(video_stream['width'])
                height = int(video_stream['height'])
            
            # Рассчитываем новые параметры С УЧЕТОМ МИНИМАЛЬНОЙ ВЫСОТЫ
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            # ДОБАВЛЯЕМ ПРОВЕРКУ МИНИМАЛЬНОЙ ВЫСОТЫ
            min_height = 240  # Минимальная высота в пикселях
            if new_height < min_height: # Сохраняем пропорции, но не уменьшаем ниже min_height
                new_width = width
                new_height = height
           
            # Убеждаемся что размеры четные
            new_width = new_width // 2 * 2
            new_height = new_height // 2 * 2
            
            # КОМАНДА FFMPEG
            cmd = [
                "ffmpeg", 
                "-i", input_path, 
                "-y",
                
                # Видео настройки
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", str(crf_value),
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={new_width}:{new_height}:flags=lanczos",
                "-profile:v", "high",
                "-level", "4.0",
                "-tune", "film",
                "-x264opts", "merange=24:b-adapt=2",
                
                # Аудио настройки
                "-c:a", "aac",
                "-b:a", "64k",
                "-ac", "2",
                "-ar", "48000",
                "-profile:a", "aac_low",
                
                # Дополнительные настройки
                "-movflags", "+faststart",
                "-threads", "2",  # Ограничиваем потоки FFmpeg
                output_path
            ]
            
            # Если нужно обрезать по времени
            if duration > max_duration:
                start_time = max(0, (duration - max_duration) / 2)
                cmd = cmd[:1] + ["-ss", str(start_time), "-t", str(max_duration)] + cmd[1:]
            
            # Запускаем сжатие
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if process.returncode != 0:
                raise Exception(f"Ошибка FFmpeg: {process.stderr}")
            
            # Проверяем что выходной файл создан и не пустой
            if not os.path.exists(output_path):
                raise Exception("Выходной файл не создан после сжатия")
            
            if os.path.getsize(output_path) == 0:
                raise Exception("Выходной файл пустой")
            
            # Заменяем оригинальный файл сжатой версией
            shutil.move(output_path, input_path)
            
            print(f"Успешно сжато: {os.path.basename(input_path)}")
            return True
            
        except Exception as e:
            print(f"Ошибка при сжатии {input_path}: {e}")
            
            # Восстановление из backup
            if 'backup_path' in locals() and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, input_path)
                    print(f"Восстановлен оригинал из backup")
                except Exception as restore_error:
                    print(f"Ошибка восстановления: {restore_error}")
            
            # Удаляем временные файлы
            if 'output_path' in locals() and output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            raise


# ----------------------------- MAIN -----------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = GameApp(root)
    root.mainloop()