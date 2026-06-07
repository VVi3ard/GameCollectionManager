import tkinter as tk
from tkinter import ttk, messagebox, Text
from PIL import Image, ImageTk
from checked_items import CheckedItemsManager
from video_handler import compress_video
from video_player import play_video, stop_video
from translation import translate_text, needs_translation
import os
import threading
import time
import json

class GameAppUI:
    def __init__(self, root, games, systems, rom_dir):
        self.root = root
        self.root.title("Game List Manager")
        self.root.minsize(1100, 700)
        
        self.rom_dir = rom_dir
        self.games = games
        self.systems = systems
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.app_dir)
        self.window_state_path = os.path.join(self.project_root, "window_state.json")
        self.checked_manager = CheckedItemsManager(self, os.path.join(self.rom_dir, 'checked'))
        
        self.current_game = None
        self.original_image = None
        self.video_player = None
        self.video_label = None
        self.video_timer = None
        self.video_delay = 2.0  # Задержка перед загрузкой видео (2 секунды)
        self.pending_video_path = None
        self._last_media_size = (0, 0)
        self.current_video_aspect = None
        
        self.setup_ui()
        self.apply_initial_window_geometry()
        self.checked_manager.load_checked()
        
        # Автосохранение при закрытии окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """Обработка закрытия окна - автосохранение"""
        self.checked_manager.save_checked(silent=True)
        self.save_window_state()
        self.root.destroy()

    def get_screen_bounds(self):
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        return screen_width, screen_height

    def clamp_window_geometry(self, width, height, x=None, y=None):
        screen_width, screen_height = self.get_screen_bounds()

        max_width = max(screen_width - 80, self.root.minsize()[0])
        max_height = max(screen_height - 120, self.root.minsize()[1])

        width = min(max(width, self.root.minsize()[0]), max_width)
        height = min(max(height, self.root.minsize()[1]), max_height)

        if x is None:
            x = max((screen_width - width) // 2, 0)
        else:
            x = min(max(x, 0), max(screen_width - width, 0))

        if y is None:
            y = max((screen_height - height) // 2, 0)
        else:
            y = min(max(y, 0), max(screen_height - height, 0))

        return width, height, x, y

    def apply_initial_window_geometry(self):
        default_width = 1400
        default_height = 900

        saved_state = self.load_window_state()
        if saved_state:
            width = saved_state.get("width", default_width)
            height = saved_state.get("height", default_height)
            x = saved_state.get("x")
            y = saved_state.get("y")
        else:
            width = default_width
            height = default_height
            x = None
            y = None

        width, height, x, y = self.clamp_window_geometry(width, height, x, y)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def load_window_state(self):
        if not os.path.exists(self.window_state_path):
            return None

        try:
            with open(self.window_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not all(key in data for key in ("width", "height", "x", "y")):
                return None
            return data
        except Exception:
            return None

    def save_window_state(self):
        try:
            self.root.update_idletasks()
            state = {
                "width": self.root.winfo_width(),
                "height": self.root.winfo_height(),
                "x": self.root.winfo_x(),
                "y": self.root.winfo_y(),
            }
            with open(self.window_state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=True, indent=2)
        except Exception as e:
            print(f"Error saving window state: {e}")

    def on_media_frame_resize(self, event):
        width = max(event.width, 1)
        height = max(event.height, 1)
        current_size = (width, height)
        if current_size == self._last_media_size:
            return

        self._last_media_size = current_size

        image_height, video_height = self.calculate_media_heights(width, height)
        video_width, video_x = self.calculate_video_width(width, video_height)

        self.image_frame.place(x=0, y=0, width=width, height=image_height)
        self.video_frame.place(x=video_x, y=image_height + 10, width=video_width, height=video_height)

        if self.original_image:
            self.render_current_image()

    def calculate_media_heights(self, width, height):
        gap = 10
        min_image_height = 150
        min_video_height = 150
        available_height = max(height - gap, min_image_height + min_video_height)

        image_height = max(available_height // 2, min_image_height)
        video_height = max(available_height - image_height, min_video_height)

        return image_height, video_height

    def calculate_video_width(self, media_width, video_height):
        if self.current_video_aspect and self.current_video_aspect > 0:
            target_width = min(int(video_height * self.current_video_aspect), media_width)
        else:
            target_width = media_width

        target_width = max(target_width, 1)
        video_x = max((media_width - target_width) // 2, 0)
        return target_width, video_x

    def update_media_layout(self):
        self.root.update_idletasks()
        width = max(self.media_frame.winfo_width(), 1)
        height = max(self.media_frame.winfo_height(), 1)
        self._last_media_size = (0, 0)
        self.on_media_frame_resize(type("Event", (), {"width": width, "height": height})())

    def on_video_size_detected(self, video_width, video_height):
        if video_width <= 0 or video_height <= 0:
            return

        self.current_video_aspect = video_width / video_height
        self.root.after(0, self.update_media_layout)

    def render_current_image(self):
        if not self.original_image:
            return

        self.root.update_idletasks()
        available_width = max(self.image_frame.winfo_width(), 1)
        available_height = max(self.image_frame.winfo_height(), 1)

        orig_w, orig_h = self.original_image.size
        ratio = min(available_width / orig_w, available_height / orig_h)
        new_w = max(int(orig_w * ratio), 1)
        new_h = max(int(orig_h * ratio), 1)

        resized = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        self.image_label.config(image=photo, text="")
        self.image_label.image = photo

    def setup_ui(self):
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        tree_scroll_y = ttk.Scrollbar(left_frame, orient="vertical")
        tree_scroll_x = ttk.Scrollbar(left_frame, orient="horizontal")
        self.tree = ttk.Treeview(
            left_frame, show="tree",
            yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set
        )
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)
        self.tree.column("#0", width=400, minwidth=200, stretch=True)

        self.populate_tree()

        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('*', self.on_asterisk)
        self.tree.bind('/', self.on_slash)  # Обработка / для группы

        self.right_frame = ttk.Frame(paned)
        paned.add(self.right_frame, weight=2)

        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(1, weight=1)

        self.desc_text = Text(self.right_frame, wrap=tk.WORD, height=6)
        self.desc_text.grid(row=0, column=0, sticky="ew", pady=(5, 5))

        self.media_frame = ttk.Frame(self.right_frame)
        self.media_frame.grid(row=1, column=0, sticky="nsew")
        self.media_frame.bind("<Configure>", self.on_media_frame_resize)

        self.image_frame = ttk.Frame(self.media_frame, height=320)
        self.image_frame.place(x=0, y=0, width=1, height=320)
        self.image_label = tk.Label(self.image_frame)
        self.image_label.pack(fill=tk.BOTH, expand=True)

        self.video_frame = ttk.Frame(self.media_frame, height=320)
        self.video_frame.place(x=0, y=330, width=1, height=320)

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10, fill=tk.X)
        ttk.Button(btn_frame, text="Удалить отмеченные", command=self.checked_manager.delete_checked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Перевести всё", command=self.translate_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Сохранить отметки", command=self.checked_manager.save_checked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Загрузить отметки", command=self.checked_manager.load_checked).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Сжать видео", command=lambda: compress_video(self)).pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=5)

    def populate_tree(self):
        from datetime import datetime
        clone_groups = {}
        for game in self.games:
            clone_key = game['cloneof'] or game['path']
            if clone_key not in clone_groups:
                clone_groups[clone_key] = {'main': None, 'clones': []}
            if not game['cloneof']:
                clone_groups[clone_key]['main'] = game
            else:
                clone_groups[clone_key]['clones'].append(game)

        for sys in sorted(self.systems.keys()):
            parent = self.tree.insert('', 'end', text=sys, open=True)
            for clone_key, data in sorted(clone_groups.items()):
                main_game = data['main']
                clones = data['clones']
                if main_game and main_game in self.systems[sys]:
                    year = ''
                    if main_game['releasedate']:
                        try:
                            dt = datetime.strptime(main_game['releasedate'], '%Y%m%dT%H%M%S')
                            year = dt.year
                        except ValueError:
                            year = main_game['releasedate'][:4]
                    label = f"☐ {main_game['name']} ({main_game['genre']}, {main_game['players']} players, rating {main_game['rating']}, {year})"
                    main_iid = self.tree.insert(parent, 'end', text=label, tags=('unchecked',))
                    main_game['iid'] = main_iid
                    for clone in sorted(clones, key=lambda x: x['name']):
                        clone_year = ''
                        if clone['releasedate']:
                            try:
                                dt = datetime.strptime(clone['releasedate'], '%Y%m%dT%H%M%S')
                                clone_year = dt.year
                            except ValueError:
                                clone_year = clone['releasedate'][:4]
                        clone_label = f"☐ {clone['name']} ({clone['genre']}, {clone['players']} players, rating {clone['rating']}, {clone_year})"
                        clone_iid = self.tree.insert(main_iid, 'end', text=clone_label, tags=('unchecked', 'clone'))
                        clone['iid'] = clone_iid
                elif not main_game:
                    for clone in sorted(clones, key=lambda x: x['name']):
                        if clone in self.systems[sys]:
                            year = ''
                            if clone['releasedate']:
                                try:
                                    dt = datetime.strptime(clone['releasedate'], '%Y%m%dT%H%M%S')
                                    year = dt.year
                                except ValueError:
                                    year = clone['releasedate'][:4]
                            label = f"☐ {clone['name']} ({clone['genre']}, {clone['players']} players, rating {clone['rating']}, {year})"
                            clone_iid = self.tree.insert(parent, 'end', text=label, tags=('unchecked',))
                            clone['iid'] = clone_iid
        self.checked_manager.update_checked_visuals()

    def on_select(self, event):
        item = self.tree.focus()
        if not item or self.tree.parent(item) == '' and not self.tree.get_children(item):
            return
        try:
            self.current_game = next(g for g in self.games if g.get('iid') == item)
        except StopIteration:
            return

        desc = self.current_game['desc']
        self.desc_text.delete(1.0, tk.END)
        if desc and needs_translation(desc):
            translated = translate_text(desc)
            self.desc_text.insert(tk.END, translated)
        else:
            self.desc_text.insert(tk.END, desc if desc else "Нет описания")

        if self.current_game['image']:
            img_path = os.path.join(self.rom_dir, self.current_game['image'])
            print(f"Loading image: {img_path}")
            if os.path.exists(img_path):
                try:
                    self.original_image = Image.open(img_path)
                    self.render_current_image()
                except Exception as e:
                    print(f"Error loading image: {e}")
                    self.image_label.config(image=None, text=f"Ошибка загрузки изображения: {e}")
            else:
                print(f"Image not found: {img_path}")
                self.image_label.config(image=None, text="Image not found")
        else:
            self.original_image = None
            self.image_label.config(image=None, text="No image")

        # Отменяем предыдущую задержку видео
        if self.video_timer:
            self.video_timer.cancel()
            self.video_timer = None

        # Останавливаем текущее видео
        stop_video(self)
        self.current_video_aspect = None
        self.update_media_layout()

        if self.current_game['video']:
            video_path = os.path.join(self.rom_dir, self.current_game['video'])
            print(f"Scheduling video load after {self.video_delay} seconds: {video_path}")
            
            # Запускаем таймер для отложенной загрузки видео
            self.pending_video_path = video_path
            self.video_timer = threading.Timer(self.video_delay, self.load_video_delayed)
            self.video_timer.daemon = True
            self.video_timer.start()
        else:
            print("No video specified for this game")
            # Очищаем видео-фрейм, но не добавляем никаких сообщений
            for widget in self.video_frame.winfo_children():
                widget.destroy()

    def load_video_delayed(self):
        """Загрузка видео после задержки"""
        if self.pending_video_path and os.path.exists(self.pending_video_path):
            print(f"Loading delayed video: {self.pending_video_path}")
            try:
                play_video(self, self.pending_video_path)
            except Exception as e:
                print(f"Error playing video: {e}")
                # Не показываем сообщения об ошибке - просто очищаем фрейм
                for widget in self.video_frame.winfo_children():
                    widget.destroy()
        else:
            print(f"Video not found or cancelled: {self.pending_video_path}")

    def on_asterisk(self, event):
        """Обработка нажатия * - переключение флажков и переход к следующей записи"""
        selected_items = self.tree.selection()
        if not selected_items:
            print("No items selected for *")
            return
        
        print(f"Processing * for selected items: {selected_items}")
        
        # Переключаем флажки для всех выбранных элементов
        for item in selected_items:
            if not item:
                print(f"Skipping invalid item: {item}")
                continue
            
            # Определяем, является ли элемент группой (имеет дочерние элементы)
            has_children = bool(self.tree.get_children(item))
            print(f"Item {item}: has_children={has_children}, text={self.tree.item(item, 'text')}")
            
            # Переключаем флажок для текущего элемента
            self.checked_manager.toggle_check(event, item, is_clone=not has_children)
        
        # Определяем следующий элемент для перехода
        # Берем последний выбранный элемент как точку отсчета
        last_item = selected_items[-1]
        parent = self.tree.parent(last_item)
        siblings = self.tree.get_children(parent)
        
        # Находим индекс последнего выбранного элемента среди его соседей
        if last_item in siblings:
            last_index = siblings.index(last_item)
            next_index = last_index + 1
            
            if next_index < len(siblings):
                # Переходим к следующему элементу на том же уровне
                next_item = siblings[next_index]
                self.tree.selection_set(next_item)
                self.tree.focus(next_item)
                self.tree.see(next_item)
                print(f"Moved to next item: {self.tree.item(next_item, 'text')}")
            else:
                # Если это последний элемент на уровне, ищем следующий родительский уровень
                self.move_to_next_parent_level(parent)
        else:
            # Если элемент не найден среди соседей, пытаемся найти следующий элемент
            self.move_to_next_parent_level(parent)

    def on_slash(self, event):
        """Обработка нажатия / - переключение флажка только для группы"""
        selected_items = self.tree.selection()
        if not selected_items:
            print("No items selected for /")
            return
        
        print(f"Processing / for selected items: {selected_items}")
        
        # Переключаем флажки только для групп
        for item in selected_items:
            if not item:
                print(f"Skipping invalid item: {item}")
                continue
            
            # Проверяем, является ли элемент группой (имеет дочерние элементы)
            has_children = bool(self.tree.get_children(item))
            if has_children:
                print(f"Toggling group only for: {self.tree.item(item, 'text')}")
                self.checked_manager.toggle_group_only(event, item)
            else:
                print(f"Item is not a group, skipping: {self.tree.item(item, 'text')}")
        
        # Переход к следующему элементу (аналогично *)
        last_item = selected_items[-1]
        parent = self.tree.parent(last_item)
        siblings = self.tree.get_children(parent)
        
        if last_item in siblings:
            last_index = siblings.index(last_item)
            next_index = last_index + 1
            
            if next_index < len(siblings):
                next_item = siblings[next_index]
                self.tree.selection_set(next_item)
                self.tree.focus(next_item)
                self.tree.see(next_item)
                print(f"Moved to next item: {self.tree.item(next_item, 'text')}")
            else:
                self.move_to_next_parent_level(parent)
        else:
            self.move_to_next_parent_level(parent)

    def move_to_next_parent_level(self, current_parent):
        """Переход к следующему элементу на уровне родителей"""
        if current_parent:
            # Находим соседей текущего родителя
            grand_parent = self.tree.parent(current_parent)
            parent_siblings = self.tree.get_children(grand_parent) if grand_parent else self.tree.get_children('')
            
            if current_parent in parent_siblings:
                current_index = parent_siblings.index(current_parent)
                next_parent_index = current_index + 1
                
                if next_parent_index < len(parent_siblings):
                    next_parent = parent_siblings[next_parent_index]
                    # Берем первый дочерний элемент следующего родителя
                    children = self.tree.get_children(next_parent)
                    if children:
                        next_item = children[0]
                        self.tree.selection_set(next_item)
                        self.tree.focus(next_item)
                        self.tree.see(next_item)
                        print(f"Moved to first child of next parent: {self.tree.item(next_item, 'text')}")
                    else:
                        # Если у родителя нет детей, выбираем самого родителя
                        self.tree.selection_set(next_parent)
                        self.tree.focus(next_parent)
                        self.tree.see(next_parent)
                        print(f"Moved to next parent: {self.tree.item(next_parent, 'text')}")

    def translate_all(self):
        from translation import translate_all
        translate_all(self)
