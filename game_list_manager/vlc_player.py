import tkinter as tk
import vlc
import os
import threading
import time

class VLCVideoPlayer:
    def __init__(self):
        self.instance = vlc.Instance("--no-xlib")  # Без X11 для Linux
        self.player = self.instance.media_player_new()
        self.current_path = None
        self.is_playing = False
        self.video_frame = None

    def detect_video_size(self, app, retries=20):
        if not self.is_playing:
            return

        video_size = self.player.video_get_size(0)
        if video_size and video_size[0] > 0 and video_size[1] > 0:
            if hasattr(app, "on_video_size_detected"):
                app.on_video_size_detected(video_size[0], video_size[1])
            return

        if retries > 0:
            app.root.after(100, self.detect_video_size, app, retries - 1)
        
    def play_video(self, app, path):
        """Воспроизведение видео с помощью VLC"""
        print(f"Attempting to play video with VLC: {path}")
        
        try:
            self.stop_video(app)
            
            if not os.path.exists(path):
                raise FileNotFoundError(f"Видео файл не найден: {path}")
            
            # Создаем фрейм для видео
            self.video_frame = tk.Frame(app.video_frame, bg='black')
            self.video_frame.pack(fill=tk.BOTH, expand=True)
            
            # Получаем ID окна для встраивания
            window_id = self.video_frame.winfo_id()
            
            # Устанавливаем окно для воспроизведения
            if os.name == 'nt':  # Windows
                self.player.set_hwnd(window_id)
            else:  # Linux/Mac
                self.player.set_xwindow(window_id)
            
            # Создаем медиа объект
            media = self.instance.media_new(path)
            self.player.set_media(media)
            
            # Настраиваем параметры воспроизведения
            self.player.set_rate(1.0)  # Нормальная скорость
            self.player.video_set_scale(0)  # Автомасштабирование
            self.player.audio_set_volume(100)  # Максимальная громкость
            
            # Запускаем воспроизведение
            self.player.play()
            self.current_path = path
            self.is_playing = True
            app.root.after(200, self.detect_video_size, app)
            
            # Мониторим состояние воспроизведения
            self.monitor_playback(app)
            
            app.video_player = {
                'player': self,
                'running': True,
                'frame': self.video_frame,
                'path': path
            }
            
            print(f"VLC video playback started: {path}")
            
        except Exception as e:
            print(f"Error in VLC play_video: {e}")
            self.stop_video(app)
            self.show_error(app, f"Ошибка VLC: {e}")
    
    def monitor_playback(self, app):
        """Мониторинг состояния воспроизведения"""
        def monitor():
            while self.is_playing and self.player.is_playing():
                time.sleep(0.1)
            
            if self.is_playing:
                # Видео завершилось или произошла ошибка
                app.root.after(0, self.on_playback_end, app)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def on_playback_end(self, app):
        """Обработка завершения воспроизведения"""
        print("Video playback ended")
        # Можно реализовать автоповтор или следующее видео
    
    def stop_video(self, app):
        """Остановка воспроизведения"""
        self.is_playing = False
        self.current_path = None
        
        if self.player.is_playing():
            self.player.stop()
        
        if self.video_frame:
            try:
                self.video_frame.destroy()
            except:
                pass
            self.video_frame = None
        
        if hasattr(app, 'video_player'):
            app.video_player = None
        
        print("VLC video playback stopped")
    
    def show_error(self, app, message):
        """Показать сообщение об ошибке"""
        for widget in app.video_frame.winfo_children():
            widget.destroy()
        
        error_label = tk.Label(app.video_frame, text=message, fg='red', wraplength=300)
        error_label.pack(fill=tk.BOTH, expand=True)
        app.video_label = error_label

# Глобальный экземпляр VLC плеера
vlc_player = VLCVideoPlayer()

def play_video_vlc(app, path):
    """Функция для воспроизведения видео через VLC"""
    vlc_player.play_video(app, path)

def stop_video_vlc(app):
    """Функция для остановки видео через VLC"""
    vlc_player.stop_video(app)

def is_vlc_available():
    """Проверка доступности VLC"""
    try:
        import vlc
        return True
    except ImportError:
        return False
