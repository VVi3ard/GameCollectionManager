import tkinter as tk
from tkinter import filedialog
from ui import GameAppUI
from xml_handler import load_gamelist
import os

def select_directory():
    root = tk.Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title="Select ROM Directory")
    root.destroy()
    return directory

def main():
    rom_dir = select_directory()
    if not rom_dir:
        print("No directory selected. Exiting.")
        return
    
    xml_path = os.path.join(rom_dir, 'gamelist.xml')
    if not os.path.exists(xml_path):
        print(f"gamelist.xml not found in {rom_dir}")
        return
    
    games, systems = load_gamelist(xml_path)
    if not games:
        print("No games loaded. Exiting.")
        return
    
    root = tk.Tk()
    app = GameAppUI(root, games, systems, rom_dir)
    root.mainloop()

if __name__ == "__main__":
    main()