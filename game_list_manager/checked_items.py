import os
import threading
import xml.etree.ElementTree as ET
from tkinter import messagebox


class CheckedItemsManager:
    def __init__(self, app, checked_dir):
        self.app = app
        self.checked_dir = os.path.normpath(checked_dir)
        if not os.path.exists(self.checked_dir):
            try:
                os.makedirs(self.checked_dir)
                print(f"Created directory: {self.checked_dir}")
            except Exception as e:
                print(f"Error creating directory {self.checked_dir}: {e}")
        self.checked_items = set()
        self.save_timer = None
        self.save_delay = 2
        self.save_pending = False

    def _valid_paths(self):
        return set(self.app.all_paths)

    def toggle_item(self, item):
        meta = self.app.node_meta.get(item)
        if not meta:
            return

        item_type = meta.get("type")
        if item_type == "game":
            path = meta["path"]
            if path in self.checked_items:
                self.checked_items.remove(path)
            else:
                self.checked_items.add(path)
        elif item_type in {"group", "version_group"}:
            paths = set(meta.get("paths", []))
            if not paths:
                return
            if paths.issubset(self.checked_items):
                self.checked_items.difference_update(paths)
            else:
                self.checked_items.update(paths)

        self.schedule_autosave()
        self.update_checked_visuals()

    def set_item_checked(self, item, checked):
        meta = self.app.node_meta.get(item)
        if not meta:
            return

        item_type = meta.get("type")
        if item_type == "game":
            paths = {meta["path"]}
        elif item_type in {"group", "version_group"}:
            paths = set(meta.get("paths", []))
        else:
            paths = set()

        if not paths:
            return

        if checked:
            self.checked_items.update(paths)
        else:
            self.checked_items.difference_update(paths)

        self.schedule_autosave()
        self.update_checked_visuals()

    def set_only_one_version(self, version_paths, keep_path):
        version_paths = set(version_paths)
        self.checked_items.update(version_paths)
        if keep_path in self.checked_items:
            self.checked_items.remove(keep_path)
        self.schedule_autosave()
        self.update_checked_visuals()

    def schedule_autosave(self):
        if self.save_timer:
            self.save_timer.cancel()

        self.save_timer = threading.Timer(self.save_delay, self.autosave)
        self.save_timer.daemon = True
        self.save_timer.start()
        self.save_pending = True

    def autosave(self):
        if self.save_pending:
            self.save_checked(silent=True)
            self.save_pending = False

    def save_checked(self, silent=False):
        try:
            os.makedirs(self.checked_dir, exist_ok=True)
            file_path = os.path.join(self.checked_dir, 'checked.txt')
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in sorted(self.checked_items):
                    f.write(item + '\n')
            if not silent:
                print(f"Saved checked items to {file_path}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Ошибка", f"Не удалось сохранить отметки: {e}")
            print(f"Error saving checked items: {e}")

    def load_checked(self):
        try:
            file_path = os.path.join(self.checked_dir, 'checked.txt')
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_items = {line.strip() for line in f if line.strip()}
                self.checked_items = loaded_items & self._valid_paths()
                print(f"Loaded checked items from {file_path}")
            else:
                self.checked_items = set()
            self.update_checked_visuals()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить отметки: {e}")
            print(f"Error loading checked items: {e}")

    def update_checked_visuals(self):
        self.checked_items.intersection_update(self._valid_paths())
        self.app.refresh_tree_checkmarks()
        print("Updated checked visuals")

    def exclude_checked(self):
        if not self.checked_items:
            messagebox.showinfo("Информация", "Нет отмеченных игр для исключения")
            print("No checked items to exclude")
            return

        try:
            tree = ET.parse(self.app.curated_xml_path)
            root = tree.getroot()
            paths_to_exclude = set(self.checked_items)
            games_to_remove = []

            for game in root.findall('game'):
                path_elem = game.find('path')
                game_path = path_elem.text if path_elem is not None else ''
                if game_path in paths_to_exclude:
                    games_to_remove.append(game)

            for game in games_to_remove:
                root.remove(game)
                removed_path = game.find('path').text if game.find('path') is not None else ''
                print(f"Excluded game from curated XML: {removed_path}")

            tree.write(self.app.curated_xml_path, encoding='utf-8', xml_declaration=True)
            print(f"Updated curated XML: {self.app.curated_xml_path}")

            self.checked_items.difference_update(paths_to_exclude)
            self.save_checked(silent=True)
            self.app.reload_all_data(rebuild_cache=True)

            messagebox.showinfo("Успех", "Отмеченные игры исключены из curated XML")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось исключить игры: {e}")
            print(f"Error excluding checked items: {e}")
