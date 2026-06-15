import json
import os
import threading
import tkinter as tk
from tkinter import Text, filedialog, messagebox, ttk

from PIL import Image, ImageTk

from checked_items import CheckedItemsManager
from db_cache import (
    ensure_cache,
    get_field_label,
    get_game_details,
    get_groupable_fields,
    get_version_candidates,
    load_tree_rows,
    rebuild_cache,
)
from translation import needs_translation, translate_text
from video_handler import compress_video
from video_player import play_video, stop_video
from xml_handler import export_curated_collection


CHECK_OFF = "☐"
CHECK_ON = "☑"
CHECK_PARTIAL = "▣"


class GameAppUI:
    def __init__(self, root, games, systems, rom_dir, workspace):
        self.root = root
        self.root.title("Game List Manager")
        self.root.minsize(1100, 700)

        self.rom_dir = rom_dir
        self.games = games
        self.systems = systems
        self.source_xml_path = workspace["source_xml_path"]
        self.checked_dir = workspace["checked_dir"]
        self.curated_xml_path = workspace["curated_xml_path"]
        self.project_state_path = workspace["project_state_path"]
        self.cache_db_path = workspace["cache_db_path"]
        self.support_root = workspace["support_root"]
        self.export_dir = None

        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.app_dir)
        self.window_state_path = os.path.join(self.project_root, "window_state.json")

        self.grouping_fields = ["system", "", ""]
        self.groupable_fields = []
        self.field_name_to_display = {"": "Нет"}
        self.field_display_to_name = {"Нет": ""}
        self.all_rows = []
        self.tree_rows = []
        self.all_paths = set()
        self.node_meta = {}
        self.grouping_vars = []
        self.grouping_combos = []

        self.checked_manager = CheckedItemsManager(self, self.checked_dir)

        self.current_game = None
        self._current_preview_key = None
        self._preview_generation = 0
        self.original_image = None
        self.video_player = None
        self.video_label = None
        self.video_timer = None
        self.video_delay = 2.0
        self.pending_video_path = None
        self._last_media_size = (0, 0)
        self.current_video_aspect = None

        self.load_project_state()
        self.initialize_cache(force_rebuild=False)
        self.setup_ui()
        self.apply_initial_window_geometry()
        self.reload_all_data(rebuild_cache=False)
        self.checked_manager.load_checked()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.checked_manager.save_checked(silent=True)
        self.save_project_state()
        self.save_window_state()
        self.root.destroy()

    def initialize_cache(self, force_rebuild=False):
        if force_rebuild:
            rebuild_cache(self.curated_xml_path, self.cache_db_path, self.support_root)
        else:
            ensure_cache(self.curated_xml_path, self.cache_db_path, self.support_root)

        self.groupable_fields = get_groupable_fields(self.cache_db_path)
        self.field_name_to_display = {"": "Нет"}
        self.field_display_to_name = {"Нет": ""}
        for field in self.groupable_fields:
            label = get_field_label(field)
            display = label if label not in self.field_display_to_name else f"{label} [{field}]"
            self.field_name_to_display[field] = display
            self.field_display_to_name[display] = field

        self.grouping_fields = [
            field if field in self.groupable_fields or field == "" else ""
            for field in self.grouping_fields
        ]

    def get_screen_bounds(self):
        self.root.update_idletasks()
        return self.root.winfo_screenwidth(), self.root.winfo_screenheight()

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

    def geometry_over_widget(self, widget, width, height):
        self.root.update_idletasks()
        screen_width, screen_height = self.get_screen_bounds()
        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_width = max(widget.winfo_width(), 1)
        widget_height = max(widget.winfo_height(), 1)

        x = widget_x + (widget_width - width) // 2
        y = widget_y + (widget_height - height) // 2
        x = min(max(x, 0), max(screen_width - width, 0))
        y = min(max(y, 0), max(screen_height - height, 0))
        return f"{width}x{height}+{x}+{y}"

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

    def load_project_state(self):
        if not os.path.exists(self.project_state_path):
            return

        try:
            with open(self.project_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            export_dir = data.get("export_dir")
            if export_dir:
                self.export_dir = export_dir
            grouping_fields = data.get("grouping_fields")
            if isinstance(grouping_fields, list):
                fields = grouping_fields[:3] + ["", "", ""]
                self.grouping_fields = fields[:3]
        except Exception as e:
            print(f"Error loading project state: {e}")

    def save_project_state(self):
        try:
            data = {
                "export_dir": self.export_dir,
                "curated_xml_path": self.curated_xml_path,
                "grouping_fields": self.grouping_fields,
            }
            with open(self.project_state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)
        except Exception as e:
            print(f"Error saving project state: {e}")

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
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(1, weight=1)

        grouping_frame = ttk.LabelFrame(left_frame, text="Группировка")
        grouping_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        for idx in range(3):
            ttk.Label(grouping_frame, text=f"Уровень {idx + 1}").grid(row=0, column=idx, sticky="w", padx=4, pady=4)
            var = tk.StringVar(value=self.field_name_to_display.get(self.grouping_fields[idx], "Нет"))
            combo = ttk.Combobox(
                grouping_frame,
                textvariable=var,
                state="readonly",
                values=list(self.field_display_to_name.keys()),
                width=26,
            )
            combo.grid(row=1, column=idx, sticky="ew", padx=4, pady=4)
            self.grouping_vars.append(var)
            self.grouping_combos.append(combo)

        ttk.Button(grouping_frame, text="Применить", command=self.apply_grouping).grid(row=1, column=3, padx=4, pady=4)
        ttk.Button(grouping_frame, text="Перестроить индекс", command=self.rebuild_index).grid(row=1, column=4, padx=4, pady=4)

        tree_container = ttk.Frame(left_frame)
        tree_container.grid(row=1, column=0, sticky="nsew")
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        tree_scroll_y = ttk.Scrollbar(tree_container, orient="vertical")
        tree_scroll_x = ttk.Scrollbar(tree_container, orient="horizontal")
        self.tree = ttk.Treeview(
            tree_container,
            show="tree",
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
        )
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.column("#0", width=400, minwidth=200, stretch=True)

        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('*', self.on_asterisk)
        self.tree.bind('/', self.on_slash)

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

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=(8, 0))
        self.curated_xml_var = tk.StringVar()
        self.export_dir_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.curated_xml_var, wraplength=1400, justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Label(status_frame, textvariable=self.export_dir_var, wraplength=1400, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))

        controls_frame = ttk.Frame(self.root)
        controls_frame.pack(pady=10, fill=tk.X)

        curation_row = ttk.Frame(controls_frame)
        curation_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(curation_row, text="Исключить отмеченные", command=self.checked_manager.exclude_checked).pack(side=tk.LEFT, padx=5)
        ttk.Button(curation_row, text="Перевести всё", command=self.translate_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(curation_row, text="Сохранить отметки", command=self.checked_manager.save_checked).pack(side=tk.LEFT, padx=5)
        ttk.Button(curation_row, text="Загрузить отметки", command=self.checked_manager.load_checked).pack(side=tk.LEFT, padx=5)

        export_row = ttk.Frame(controls_frame)
        export_row.pack(fill=tk.X)
        ttk.Button(export_row, text="Выбрать каталог экспорта", command=self.choose_export_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_row, text="Экспорт коллекции", command=self.export_collection).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            export_row,
            text="Сжать видео в экспорте",
            command=lambda: compress_video(self, self.export_dir, "экспортированной коллекции")
        ).pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=5)

        self.refresh_project_status()

    def refresh_project_status(self):
        self.curated_xml_var.set(f"Рабочий XML: {self.curated_xml_path}")
        if self.export_dir:
            self.export_dir_var.set(f"Каталог экспорта: {self.export_dir}")
        else:
            self.export_dir_var.set("Каталог экспорта: не выбран")

    def current_grouping_fields(self):
        return [field for field in self.grouping_fields if field]

    def sync_grouping_from_ui(self):
        fields = []
        for var in self.grouping_vars:
            display = var.get() or "Нет"
            fields.append(self.field_display_to_name.get(display, ""))
        self.grouping_fields = fields

    def apply_grouping(self):
        self.sync_grouping_from_ui()
        self.save_project_state()
        self.rebuild_tree()

    def rebuild_index(self):
        self.reload_all_data(rebuild_cache=True)

    def reload_all_data(self, rebuild_cache=False):
        self.initialize_cache(force_rebuild=rebuild_cache)
        self.all_rows = load_tree_rows(self.cache_db_path, [])
        self.tree_rows = load_tree_rows(self.cache_db_path, self.current_grouping_fields())
        self.games = self.all_rows
        self.all_paths = {row["path"] for row in self.all_rows}

        if self.grouping_combos:
            combo_values = list(self.field_display_to_name.keys())
            for combo, var, field in zip(self.grouping_combos, self.grouping_vars, self.grouping_fields):
                combo["values"] = combo_values
                var.set(self.field_name_to_display.get(field, "Нет"))

        self.rebuild_tree()

    def clear_preview(self):
        self.current_game = None
        self._current_preview_key = None
        self.original_image = None
        self.pending_video_path = None
        self._preview_generation += 1

        if self.video_timer:
            self.video_timer.cancel()
            self.video_timer = None

        self.desc_text.delete(1.0, tk.END)
        self.image_label.config(image=None, text="")
        self.image_label.image = None
        stop_video(self)
        self.current_video_aspect = None
        for widget in self.video_frame.winfo_children():
            widget.destroy()
        self.update_media_layout()

    def reload_games_from_active_xml(self):
        self.reload_all_data(rebuild_cache=True)

    def rebuild_tree(self):
        self.clear_preview()
        self.tree.delete(*self.tree.get_children())
        self.node_meta = {}

        rows = self.tree_rows
        grouping_fields = self.current_grouping_fields()
        group_counts = {}
        version_counts = {}
        version_names = {}
        version_paths = {}
        version_preview_ids = {}

        for row in rows:
            prefix = []
            for field in grouping_fields:
                value = self.format_group_value(field, row.get(field))
                prefix.append((field, value))
                key = tuple(prefix)
                group_counts[key] = group_counts.get(key, 0) + 1

            parent_key = tuple(prefix)
            base_key = row.get("base_key") or row.get("path")
            version_key = (parent_key, base_key)
            version_counts[version_key] = version_counts.get(version_key, 0) + 1
            version_paths.setdefault(version_key, set()).add(row["path"])
            current_name = version_names.get(version_key)
            if row.get("is_base_version"):
                version_names[version_key] = row.get("name") or row.get("path")
                version_preview_ids[version_key] = row["db_id"]
            elif current_name is None:
                version_names[version_key] = row.get("name") or row.get("path")
                version_preview_ids[version_key] = row["db_id"]

        created_groups = {}
        created_versions = {}

        for row in rows:
            parent = ""
            prefix = []
            ancestor_ids = []
            for field in grouping_fields:
                value = self.format_group_value(field, row.get(field))
                prefix.append((field, value))
                key = tuple(prefix)
                if key not in created_groups:
                    label = f"{value} ({group_counts[key]})"
                    iid = self.tree.insert(parent, "end", text=f"{CHECK_OFF} {label}", open=False)
                    created_groups[key] = iid
                    self.node_meta[iid] = {
                        "type": "group",
                        "base_label": label,
                        "paths": set(),
                        "group_key": key,
                    }
                parent = created_groups[key]
                ancestor_ids.append(parent)

            parent_key = tuple(prefix)
            base_key = row.get("base_key") or row.get("path")
            version_key = (parent_key, base_key)
            version_iid = None
            if version_counts.get(version_key, 0) > 1:
                if version_key not in created_versions:
                    version_label = f"{version_names.get(version_key, base_key)} ({version_counts[version_key]})"
                    version_iid = self.tree.insert(parent, "end", text=f"{CHECK_OFF} {version_label}", open=True)
                    created_versions[version_key] = version_iid
                    self.node_meta[version_iid] = {
                        "type": "version_group",
                        "base_label": version_label,
                        "paths": set(version_paths.get(version_key, set())),
                        "base_key": base_key,
                        "preview_db_id": version_preview_ids.get(version_key),
                    }
                parent = created_versions[version_key]
                ancestor_ids.append(parent)

            game_label = self.format_game_label(row)
            game_iid = self.tree.insert(parent, "end", text=f"{CHECK_OFF} {game_label}", tags=("game",))
            self.node_meta[game_iid] = {
                "type": "game",
                "base_label": game_label,
                "path": row["path"],
                "db_id": row["db_id"],
                "base_key": base_key,
            }

            for iid in ancestor_ids:
                self.node_meta[iid]["paths"].add(row["path"])

        self.checked_manager.update_checked_visuals()

    def format_group_value(self, field, value):
        if field == "mature_flag":
            return "Mature" if str(value) in {"1", "true", "True"} else "Not Mature"
        value = (value or "").strip() if isinstance(value, str) else value
        return str(value) if value not in (None, "") else "(пусто)"

    def format_game_label(self, row):
        year = row.get("year") or ""
        players = row.get("players") or ""
        rating = row.get("rating") or "0"
        genre = row.get("genre") or row.get("genre_mame") or row.get("catver_category") or "Unknown"
        return f"{row.get('name', row.get('path', ''))} ({genre}, {players} players, rating {rating}, {year})"

    def refresh_tree_checkmarks(self):
        for iid, meta in self.node_meta.items():
            item_type = meta["type"]
            if item_type == "game":
                prefix = CHECK_ON if meta["path"] in self.checked_manager.checked_items else CHECK_OFF
            else:
                paths = meta.get("paths", set())
                checked_count = len(paths & self.checked_manager.checked_items)
                if checked_count == 0:
                    prefix = CHECK_OFF
                elif checked_count == len(paths):
                    prefix = CHECK_ON
                else:
                    prefix = CHECK_PARTIAL
            self.tree.item(iid, text=f"{prefix} {meta['base_label']}")

    def choose_export_dir(self):
        directory = filedialog.askdirectory(title="Выберите каталог экспорта")
        if not directory:
            return

        source_root = os.path.abspath(self.rom_dir)
        export_root = os.path.abspath(directory)
        if os.path.normcase(source_root) == os.path.normcase(export_root):
            messagebox.showerror("Ошибка", "Каталог экспорта должен отличаться от исходной коллекции")
            return

        self.export_dir = export_root
        self.save_project_state()
        self.refresh_project_status()

    def export_collection(self):
        if not self.export_dir:
            messagebox.showinfo("Информация", "Сначала выберите каталог экспорта")
            return

        try:
            result = export_curated_collection(self.curated_xml_path, self.rom_dir, self.export_dir)
            self.save_project_state()
            self.refresh_project_status()

            missing_count = len(result["missing_files"])
            message = (
                f"Экспорт завершён\n"
                f"Игр: {result['games_count']}\n"
                f"Скопировано файлов: {result['copied_files']}\n"
                f"gamelist.xml: {result['export_xml_path']}"
            )
            if missing_count:
                message += f"\nОтсутствующих файлов: {missing_count}"

            messagebox.showinfo("Готово", message)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось экспортировать коллекцию: {e}")
            print(f"Error exporting collection: {e}")

    def load_game_preview(self, game):
        self._preview_generation += 1
        preview_generation = self._preview_generation
        self._current_preview_key = game.get("db_id") or game.get("path")

        desc = game.get("desc", "")
        self.desc_text.delete(1.0, tk.END)
        if desc and needs_translation(desc):
            translated = translate_text(desc)
            self.desc_text.insert(tk.END, translated)
        else:
            self.desc_text.insert(tk.END, desc if desc else "Нет описания")

        image_rel = game.get("image") or f"media/png/{game.get('rom_stem', '')}.png"
        if image_rel:
            img_path = os.path.join(self.rom_dir, image_rel)
            print(f"Loading image: {img_path}")
            if os.path.exists(img_path):
                try:
                    self.original_image = Image.open(img_path)
                    self.render_current_image()
                except Exception as e:
                    print(f"Error loading image: {e}")
                    self.image_label.config(image=None, text=f"Ошибка загрузки изображения: {e}")
            else:
                self.original_image = None
                self.image_label.config(image=None, text="Image not found")
        else:
            self.original_image = None
            self.image_label.config(image=None, text="No image")

        if self.video_timer:
            self.video_timer.cancel()
            self.video_timer = None

        stop_video(self)
        self.current_video_aspect = None
        self.update_media_layout()

        video_rel = game.get("video") or f"media/mp4/{game.get('rom_stem', '')}.mp4"
        if video_rel:
            video_path = os.path.join(self.rom_dir, video_rel)
            print(f"Scheduling video load after {self.video_delay} seconds: {video_path}")
            self.pending_video_path = video_path
            self.video_timer = threading.Timer(
                self.video_delay,
                self.load_video_delayed,
                args=(preview_generation, video_path),
            )
            self.video_timer.daemon = True
            self.video_timer.start()
        else:
            self.pending_video_path = None
            for widget in self.video_frame.winfo_children():
                widget.destroy()

    def on_select(self, event):
        item = self.tree.focus()
        if not item:
            return
        meta = self.node_meta.get(item)
        if not meta:
            return

        if meta["type"] == "game":
            db_id = meta.get("db_id")
        elif meta["type"] == "version_group":
            db_id = meta.get("preview_db_id")
        else:
            return

        current_key = self.current_game.get("db_id") if self.current_game else None
        if current_key is None and self.current_game:
            current_key = self.current_game.get("path")

        selected_key = db_id or meta.get("path")
        if selected_key is not None and selected_key == current_key and self._current_preview_key == selected_key:
            return

        game = get_game_details(self.cache_db_path, db_id)
        if not game:
            return

        self.current_game = game
        self.load_game_preview(game)

    def load_video_delayed(self, preview_generation, expected_path):
        if preview_generation != self._preview_generation:
            print(f"Video load skipped for stale preview: {expected_path}")
            return

        if self.pending_video_path == expected_path and os.path.exists(self.pending_video_path):
            print(f"Loading delayed video: {self.pending_video_path}")
            try:
                play_video(self, self.pending_video_path)
            except Exception as e:
                print(f"Error playing video: {e}")
                for widget in self.video_frame.winfo_children():
                    widget.destroy()
        else:
            print(f"Video not found or cancelled: {expected_path}")

    def choose_version_to_keep(self, base_key):
        candidates = get_version_candidates(self.cache_db_path, base_key)
        if not candidates:
            return None

        dialog = tk.Toplevel(self.root)
        dialog.title("Выберите версию")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry(self.geometry_over_widget(self.tree, 760, 320))

        ttk.Label(dialog, text="Выберите версию, которую нужно оставить", font=("Arial", 11, "bold")).pack(pady=10)

        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        default_index = 0
        for idx, row in enumerate(candidates):
            label = f"{row.get('name', row.get('path', ''))} | {row.get('year', '')} | {row.get('releasedate', '')}"
            listbox.insert(tk.END, label)
            if row.get("is_base_version"):
                default_index = idx

        listbox.selection_set(default_index)
        listbox.activate(default_index)
        listbox.see(default_index)
        listbox.focus_set()

        result = {"path": None}

        def confirm(event=None):
            selection = listbox.curselection()
            if not selection:
                return
            result["path"] = candidates[selection[0]]["path"]
            dialog.destroy()

        def cancel(event=None):
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Оставить выбранную", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=cancel).pack(side=tk.LEFT, padx=5)

        dialog.bind("<Return>", confirm)
        dialog.bind("<Escape>", cancel)
        listbox.bind("<Double-Button-1>", confirm)

        self.root.wait_window(dialog)
        return result["path"]

    def move_to_next_visible(self, item):
        current = item
        next_item = self.tree.next(current)
        while not next_item:
            parent = self.tree.parent(current)
            if not parent:
                return
            current = parent
            next_item = self.tree.next(current)

        self.tree.selection_set(next_item)
        self.tree.focus(next_item)
        self.tree.see(next_item)

    def handle_mark_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        last_item = selected_items[-1]
        for item in selected_items:
            self.checked_manager.set_item_checked(item, True)

        self.move_to_next_visible(last_item)

    def handle_keep_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return

        last_item = selected_items[-1]
        for item in selected_items:
            meta = self.node_meta.get(item)
            if not meta:
                continue

            if meta["type"] == "version_group":
                keep_path = self.choose_version_to_keep(meta["base_key"])
                if not keep_path:
                    return
                self.checked_manager.set_only_one_version(meta.get("paths", set()), keep_path)
            else:
                self.checked_manager.set_item_checked(item, False)

        self.move_to_next_visible(last_item)

    def on_asterisk(self, event):
        self.handle_mark_selected()
        return "break"

    def on_slash(self, event):
        self.handle_keep_selected()
        return "break"

    def translate_all(self):
        from translation import translate_all
        translate_all(self)
