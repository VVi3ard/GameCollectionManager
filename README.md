# Game Collection Manager

Desktop utility for browsing and cleaning an EmulationStation-style ROM collection with image preview, video preview, translation helpers, and batch video compression.

## Features

- Browse `gamelist.xml` as a tree grouped by system and clone families
- Preview box art and gameplay videos
- Save checked items between sessions
- Remove checked games from the XML and delete matching ROM files
- Translate descriptions from English to Russian
- Batch-compress preview videos
- Remember the last window size and position

## Repository Layout

```text
setup.bat
start.bat
game_list_manager/
```

- `setup.bat` installs Python dependencies and prepares local FFmpeg
- `start.bat` launches the application
- `game_list_manager/main.py` is the current Python entry point

## Requirements

- Windows
- Python 3.12
- Optional: VLC media player for in-app video playback

## First-Time Setup

Double-click:

```text
setup.bat
```

Or run from PowerShell:

```powershell
.\setup.bat
```

The setup script:

- creates `.venv-py312`
- installs Python packages from `game_list_manager\requirements.txt`
- downloads local FFmpeg essentials into `game_list_manager\ffmpeg\bin` when needed

## Run

Double-click:

```text
start.bat
```

Or run from PowerShell:

```powershell
.\start.bat
```

After launch the app prompts you to select the ROM collection directory that contains `gamelist.xml`.

## FFmpeg

For video compression the app checks FFmpeg in this order:

1. `.\game_list_manager\ffmpeg\bin\ffmpeg.exe` and `ffprobe.exe`
2. `ffmpeg` and `ffprobe` from the system `PATH`

In normal use you do not need to install FFmpeg manually because `setup.bat` downloads the Windows essentials build automatically.

## XML Format

The application expects a standard EmulationStation-style `gamelist.xml`, for example:

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

## Notes

- The project evolved from an older single-file version; the current maintained code lives in `game_list_manager/`
- Local runtime files such as `.venv-py312`, downloaded FFmpeg binaries, saved window state, and checked item data are ignored by git
