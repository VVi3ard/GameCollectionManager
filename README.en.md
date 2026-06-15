# Game Collection Manager

[Русская версия](README.md)

![Game Collection Manager screenshot](screenshot.png)

Desktop GUI for curating large EmulationStation-style ROM collections with image preview, gameplay video, batch translation, and bulk cleanup tools.

## Why this tool exists

If you collect ROM sets for RetroArch, MAME, FBNeo, or similar systems, the real problem is usually not the ROMs themselves. The bigger issue is scale.

A full arcade set can contain tens of thousands of games. Keeping everything makes little sense, especially on handheld devices or limited storage. ROM files are often tiny, but scraped media is not: screenshots, box art, and especially video previews can consume huge amounts of space.

This tool was built to make manual curation practical. Instead of trusting somebody else's "best of" pack, you can review the games yourself and quickly decide what stays and what goes.

## Features

- Browse a curated working XML with configurable grouping up to 3 levels
- Enrich arcade entries with MAME/CatVer metadata: categories, genres, MAME version, and mature flag
- Group multiple versions of the same game separately via `cloneof`
- Preview description, image, and gameplay video for the selected game
- Mark games for removal directly from the keyboard
- Save and restore your curation progress
- Batch-translate English descriptions into Russian
- Export a curated collection into a separate folder
- Batch-compress `.mp4` previews inside the exported collection
- Remember window size and position between sessions

## Quick start

### Requirements

- Windows
- Python 3.12
- Optional but recommended: VLC Player for in-app video playback

FFmpeg does not need to be installed manually. The setup script downloads a local essentials build automatically when needed.

On first launch, the app creates a working file next to the collection:

- `checked\curated_gamelist.xml`

The original `gamelist.xml` is left untouched.

### First-time setup

The root of the repository intentionally exposes only two user-facing files:

- `setup.bat`
- `start.bat`

Run:

1. `setup.bat`
2. Wait until dependency installation finishes
3. Let it download FFmpeg if it is missing

### Start the app

1. Run `start.bat`
2. Select the collection folder that contains `gamelist.xml`
3. Browse and curate your collection

## How to use it

Typical workflow:

1. Open the app and select your collection folder
2. Let it create or reuse `checked\curated_gamelist.xml`
3. Choose a tree grouping if needed: system, genre, year, mature flag, CatVer category, and other fields
4. Select games one by one and inspect the description, image, and video
5. Press `*` when you do not want a game in the final build
6. Press `/` when you want to keep a game and move on
7. If the selected row is a version group, `/` opens a dialog where you choose the exact version to keep
8. Press `Исключить отмеченные` to remove marked games only from `curated_gamelist.xml`
9. Choose an export directory
10. Press `Экспорт коллекции` to assemble a new physical collection from the curated XML
11. Optionally press `Сжать видео в экспорте`

### Interface layout

- Left panel: entries grouped by selected fields, with separate version groups for clone families
- Right panel: description, image, and video preview
- Bottom panel: collection management buttons
- `Группировка` panel: up to 3 tree levels, for example `System -> Genre`, `Mature -> System -> CatVer`, or `Year -> System`

There are two different group types:

- field groups: system, genre, year, mature flag, and similar metadata
- version groups: multiple versions of the same game, built from `cloneof` / `base_key`

The right preview is shown for a concrete game and for a version group. It is not shown for generic field groups because those are just containers.

### Keyboard shortcuts

- `*` — mark the selected game or the whole selected group for exclusion and move to the next row
- `/` — keep the selected game or group and move to the next row
- `/` on a version group — open the version picker; the chosen version is kept and the other versions are marked for exclusion

The intended review loop:

- do not want the game: press `*`
- want the game: press `/`
- want only one version from a clone family: select the version group, press `/`, choose the version

### Buttons

- `Исключить отмеченные` — remove marked entries only from `checked\curated_gamelist.xml`
- `Перевести всё` — batch-translate descriptions inside `checked\curated_gamelist.xml`
- `Сохранить отметки` — save the current marked set into `<collection_folder>\checked\checked.txt`
- `Загрузить отметки` — restore previously saved marks from `<collection_folder>\checked\checked.txt`
- `Выбрать каталог экспорта` — choose where the new collection will be assembled
- `Экспорт коллекции` — copy ROMs, images, videos, and other referenced files into the export folder
- `Сжать видео в экспорте` — open batch video compression for the exported collection
- `Перестроить индекс` — rebuild the local SQLite tree cache from `checked\curated_gamelist.xml` and CatVer metadata

## Safe workflow

The current version is intentionally non-destructive during curation:

- the original `gamelist.xml` stays untouched
- all curation changes are written into `checked\curated_gamelist.xml`
- the source ROM collection is not physically modified during review

Physical copying happens only when you run `Экспорт коллекции`.

## Translation

`Перевести всё`:

- scans all games with non-Cyrillic descriptions
- translates `desc` from English to Russian
- writes the result back into `checked\curated_gamelist.xml`

Before translation, the app creates XML backups such as:

- `gamelist.bak`
- `gamelist.bak1`
- `gamelist.bak2`

## Export

Export uses `checked\curated_gamelist.xml` and builds a new collection folder:

- copies ROM files
- copies images, videos, and other file references from the XML
- writes a new `gamelist.xml` into the destination folder

The chosen export directory is shown in the UI and stored in:

- `checked\project_state.json`

## Video compression

`Сжать видео в экспорте` compresses preview videos inside the exported collection.

The batch compression tool:

- rescales videos by a configurable factor
- re-encodes video to H.264
- re-encodes audio to AAC
- can trim long previews to a maximum duration
- can process multiple files in parallel

Before replacing a file, the original video is copied into a `backup` subfolder.

FFmpeg is resolved in this order:

1. `game_list_manager\ffmpeg\bin\ffmpeg.exe` and `ffprobe.exe`
2. system `PATH`

## Project layout

```text
setup.bat
start.bat
game_list_manager/
```

- `setup.bat` — first-time setup
- `start.bat` — app launcher
- `game_list_manager/main.py` — current Python entry point
- `game_list_manager/requirements.txt` — Python dependencies
- `checked/curated_gamelist.xml` — working curated XML
- `checked/project_state.json` — saved export destination, tree grouping, and project state
- `checked/curated_cache.sqlite` — local SQLite cache for fast tree rendering
- `game_list_manager/pS_CatVer_287/` — bundled MAME/CatVer metadata for genres, categories, and mature flag

## Expected XML format

The application expects an EmulationStation-style `gamelist.xml`, for example:

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

## Demo

A usage walkthrough video will be added here later.
