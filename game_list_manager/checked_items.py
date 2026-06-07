import os
import xml.etree.ElementTree as ET
from tkinter import messagebox
import threading
import time

class CheckedItemsManager:
    def __init__(self, app, checked_dir):
        self.app = app  # Исправлено: было self.app = root
        self.checked_dir = checked_dir
        # Нормализуем путь и убеждаемся, что директория существует
        self.checked_dir = os.path.normpath(self.checked_dir)
        if not os.path.exists(self.checked_dir):
            try:
                os.makedirs(self.checked_dir)
                print(f"Created directory: {self.checked_dir}")
            except Exception as e:
                print(f"Error creating directory {self.checked_dir}: {e}")
        self.checked_items = set()
        self.save_timer = None
        self.save_delay = 2  # Задержка перед автосохранением (секунды)
        self.save_pending = False

    def toggle_check(self, event, item, is_clone=False):
        game = next((g for g in self.app.games if g.get('iid') == item), None)
        if game is None:
            print(f"No game found for item: {item}")
            return
        rom_path = game.get('path', '')
        print(f"Toggling check for item: {self.app.tree.item(item, 'text')}, is_clone={is_clone}")
        
        if not is_clone:
            # Это родительский элемент (узел с детьми)
            is_checked = rom_path in self.checked_items
            if is_checked:
                # Снимаем отметку с родителя и всех детей
                self.checked_items.remove(rom_path)
                self.app.tree.item(item, text=self.app.tree.item(item, 'text').replace('☑', '☐'), tags=('unchecked',))
                print(f"Unchecked parent: {rom_path}")
                
                # Снимаем отметки со всех дочерних элементов
                for child in self.app.tree.get_children(item):
                    child_game = next((g for g in self.app.games if g.get('iid') == child), None)
                    if child_game:
                        child_path = child_game.get('path', '')
                        if child_path in self.checked_items:
                            self.checked_items.remove(child_path)
                            self.app.tree.item(child, text=self.app.tree.item(child, 'text').replace('☑', '☐'), tags=('unchecked',))
                            print(f"Unchecked clone: {child_path}")
            else:
                # Ставим отметку на родителе и всех детях
                self.checked_items.add(rom_path)
                self.app.tree.item(item, text=self.app.tree.item(item, 'text').replace('☐', '☑'), tags=('checked',))
                print(f"Checked parent: {rom_path}")
                
                # Ставим отметки на всех дочерних элементах
                for child in self.app.tree.get_children(item):
                    child_game = next((g for g in self.app.games if g.get('iid') == child), None)
                    if child_game:
                        child_path = child_game.get('path', '')
                        if child_path not in self.checked_items:
                            self.checked_items.add(child_path)
                            self.app.tree.item(child, text=self.app.tree.item(child, 'text').replace('☐', '☑'), tags=('checked',))
                            print(f"Checked clone: {child_path}")
        else:
            # Это дочерний элемент (клон) или одиночная запись
            if rom_path in self.checked_items:
                self.checked_items.remove(rom_path)
                self.app.tree.item(item, text=self.app.tree.item(item, 'text').replace('☑', '☐'), tags=('unchecked',))
                print(f"Unchecked item: {rom_path}")
            else:
                self.checked_items.add(rom_path)
                self.app.tree.item(item, text=self.app.tree.item(item, 'text').replace('☐', '☑'), tags=('checked',))
                print(f"Checked item: {rom_path}")
        
        # Запускаем отложенное автосохранение
        self.schedule_autosave()

    def schedule_autosave(self):
        """Запланировать автосохранение через заданное время"""
        if self.save_timer:
            self.save_timer.cancel()
        
        self.save_timer = threading.Timer(self.save_delay, self.autosave)
        self.save_timer.daemon = True
        self.save_timer.start()
        self.save_pending = True

    def autosave(self):
        """Автоматическое сохранение отметок"""
        if self.save_pending:
            self.save_checked(silent=True)
            self.save_pending = False

    def update_checked_visuals(self):
        for game in self.app.games:
            rom_path = game.get('path', '')
            if 'iid' in game:
                if rom_path in self.checked_items:
                    self.app.tree.item(game['iid'], text=self.app.tree.item(game['iid'], 'text').replace('☐', '☑'), tags=('checked',))
                else:
                    self.app.tree.item(game['iid'], text=self.app.tree.item(game['iid'], 'text').replace('☑', '☐'), tags=('unchecked',))
        print("Updated checked visuals")

    def save_checked(self, silent=False):
        """Сохранение отметок с возможностью тихого режима"""
        try:
            # Убеждаемся, что директория существует
            if not os.path.exists(self.checked_dir):
                os.makedirs(self.checked_dir)
            
            file_path = os.path.join(self.checked_dir, 'checked.txt')
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in self.checked_items:
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
                    self.checked_items = set(line.strip() for line in f if line.strip())
                self.update_checked_visuals()
                print(f"Loaded checked items from {file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить отметки: {e}")
            print(f"Error loading checked items: {e}")

    def delete_checked(self):
        if not self.checked_items:
            messagebox.showinfo("Информация", "Нет отмеченных игр для удаления")
            print("No checked items to delete")
            return

        xml_path = os.path.join(self.app.rom_dir, 'gamelist.xml')
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            games_to_remove = [game for game in root.findall('game') if game.find('path').text in self.checked_items]
            
            for game in games_to_remove:
                root.remove(game)
                print(f"Removed game from gamelist.xml: {game.find('path').text}")
            
            tree.write(xml_path, encoding='utf-8', xml_declaration=True)
            print(f"Updated gamelist.xml: {xml_path}")
            
            for rom_path in self.checked_items:
                full_path = os.path.join(self.app.rom_dir, rom_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    print(f"Deleted ROM file: {full_path}")
            
            self.checked_items.clear()
            self.app.games[:] = [g for g in self.app.games if g.get('path', '') not in self.checked_items]
            for sys in self.app.systems:
                self.app.systems[sys][:] = [g for g in self.app.systems[sys] if g.get('path', '') not in self.checked_items]
            
            for item in self.app.tree.get_children():
                self.app.tree.delete(item)
            self.app.populate_tree()
            print("Refreshed tree after deletion")
            
            # Сохраняем изменения в файл отметок
            self.save_checked(silent=True)
            
            messagebox.showinfo("Успех", "Отмеченные игры удалены")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить игры: {e}")
            print(f"Error deleting checked items: {e}")

    def toggle_group_only(self, event, item):
        """Переключение флажка только для группы (родителя) без изменения детей"""
        game = next((g for g in self.app.games if g.get('iid') == item), None)
        if game is None:
            print(f"No game found for item: {item}")
            return
        
        rom_path = game.get('path', '')
        has_children = bool(self.app.tree.get_children(item))
        
        if not has_children:
            print(f"Item is not a group: {item}")
            return
        
        print(f"Toggling group only for: {self.app.tree.item(item, 'text')}")
        
        # Переключаем только родителя
        if rom_path in self.checked_items:
            self.checked_items.remove(rom_path)
            self.app.tree.item(item, text=self.app.tree.item(item, 'text').replace('☑', '☐'), tags=('unchecked',))
            print(f"Unchecked group only: {rom_path}")
        else:
            self.checked_items.add(rom_path)
            self.app.tree.item(item, text=self.app.tree.item(item, 'text').replace('☐', '☑'), tags=('checked',))
            print(f"Checked group only: {rom_path}")
        
        # Запускаем отложенное автосохранение
        self.schedule_autosave()