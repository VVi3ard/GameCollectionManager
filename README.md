# Game Collection Manager 🎮

Утилита для управления коллекцией retro-игр с поддержкой перевода описаний, управления файлами и визуального просмотра.

## ✨ Возможности

- 📁 Управление коллекцией игр из XML файлов
- 🌐 Автоматический перевод описаний с английского на русский
- 🎬 Просмотр изображений и видео игр
- ✅ Система отметок с сохранением между сессиями
- 🗑️ Удаление игр с очисткой файлов (ROMs, изображения, видео)
- 📊 Статистика перевода с расчетом ETA

## 🛠️ Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/GameCollectionManager.git
cd GameCollectionManager
```
Установите зависимости:
pip install -r requirements.txt

📦 Зависимости
См. requirements.txt:
text
tkinter
Pillow
googletrans==4.0.0-rc1
tkvideo
openpyxl

🚀 Использование
Подготовьте файл gamelist.xml в формате EmulationStation
Разместите медиафайлы в соответствующих папках

Запустите приложение:
python collection.py

🎯 Особенности
Батчевый перевод: Групповой перевод до 10 игр за запрос
Сохранение состояния: Автосохранение отметок между запусками
Предпросмотр: Встроенный просмотр изображений и видео
Резервное копирование: Автоматические бэкапы XML файла

📋 Формат XML
Приложение работает с стандартным форматом EmulationStation:
```xml
<gameList>
  <game id="123456789">
    <path>roms/game.zip</path>
    <name>Game Title</name>
    <desc>Game description</desc>
    <image>media/images/game.png</image>
    <video>media/videos/game.mp4</video>
    <rating>0.8</rating>
    <releasedate>19920101T000000</releasedate>
  </game>
</gameList>
```

🎨 Интерфейс
https://images/screenshot.png
Левая панель: Дерево игр с системами
Правая панель: Описание, изображение, видео
Нижняя панель: Кнопки управления и прогресс-бар

⚙️ Настройка
Разместите ROM файлы в папке roms/
Изображения в media/images/
Видео в media/videos/
Настройте пути в gamelist.xml

🤝 Contributing
Форкните репозиторий
Создайте feature branch: git checkout -b feature/new-feature
Коммит: git commit -am 'Add new feature'
Пуш: git push origin feature/new-feature
Создайте Pull Request
