# Game Collection Manager

[Русская версия](README.md)

![Game Collection Manager screenshot](screenshot.png)

Desktop GUI for curating large EmulationStation-style ROM collections with image preview, gameplay video, batch translation, and bulk cleanup tools.

## Why this tool exists

If you collect ROM sets for RetroArch, MAME, FBNeo, or similar systems, the real problem is usually not the ROMs themselves. The bigger issue is scale.

A full arcade set can contain tens of thousands of games. Keeping everything makes little sense, especially on handheld devices or limited storage. ROM files are often tiny, but scraped media is not: screenshots, box art, and especially video previews can consume huge amounts of space.

This tool was built to make manual curation practical. Instead of trusting somebody else's "best of" pack, you can review the games yourself and quickly decide what stays and what goes.

## Features

- Browse `gamelist.xml` as a tree grouped by systems and clone families
- Preview description, image, and gameplay video for the selected game
- Mark games for removal directly from the keyboard
- Save and restore your curation progress
- Batch-translate English descriptions into Russian
- Batch-compress `.mp4` preview videos with FFmpeg
- Remember window size and position between sessions

## Quick start

### Requirements

- Windows
- Python 3.12
- Optional but recommended: VLC Player for in-app video playback

FFmpeg does not need to be installed manually. The setup script downloads a local essentials build automatically when needed.

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
2. Expand a system in the left tree
3. Select games one by one and inspect the description, image, and video
4. Mark games you want to remove
5. When the review is complete, press `Удалить отмеченные`
6. Save your marks if you want to continue later

### Interface layout

- Left panel: systems, main games, and clone entries
- Right panel: description, image, and video preview
- Bottom panel: collection management buttons

### Keyboard shortcuts

- `*` — toggle the selected entry and move to the next one
- `*` on a parent/group entry — toggle the parent and all child clones
- `/` — toggle only the group itself without changing the child entries, then move to the next one

### Buttons

- `Удалить отмеченные` — remove marked entries from `gamelist.xml` and physically delete the matching ROM files
- `Перевести всё` — batch-translate descriptions inside `gamelist.xml`
- `Сохранить отметки` — save the current marked set into `<collection_folder>\checked\checked.txt`
- `Загрузить отметки` — restore previously saved marks from `<collection_folder>\checked\checked.txt`
- `Сжать видео` — open the batch video compression dialog

## Important safety note

`Удалить отмеченные` is a real destructive action:

- it removes entries from `gamelist.xml`
- it physically deletes the matching ROM files from disk

It does **not** currently remove related screenshots, artwork, or video previews automatically. Those media files may remain inside `media/`.

Back up your collection before large cleanup runs.

## Translation

`Перевести всё`:

- scans all games with non-Cyrillic descriptions
- translates `desc` from English to Russian
- writes the result back into `gamelist.xml`

Before translation, the app creates XML backups such as:

- `gamelist.bak`
- `gamelist.bak1`
- `gamelist.bak2`

## Video compression

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
