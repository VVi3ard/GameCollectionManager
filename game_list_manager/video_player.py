import tkinter as tk
import os

# Импортируем VLC плеер
try:
    from vlc_player import play_video_vlc, stop_video_vlc, is_vlc_available
    VLC_AVAILABLE = is_vlc_available()
except ImportError:
    VLC_AVAILABLE = False

# Резервный вариант с OpenCV
try:
    from opencv_player import play_video_opencv, stop_video_opencv, is_opencv_available
    OPENCV_AVAILABLE = is_opencv_available()
except ImportError:
    OPENCV_AVAILABLE = False

class VideoPlayerManager:
    def __init__(self):
        self.current_player = None
        print(f"Video players available: VLC={VLC_AVAILABLE}, OpenCV={OPENCV_AVAILABLE}")
    
    def play_video(self, app, path):
        """Умное воспроизведение видео с автоматическим выбором плеера"""
        print(f"Playing video: {os.path.basename(path)}")
        
        # Сначала пробуем VLC (лучшее качество + звук)
        if VLC_AVAILABLE:
            try:
                play_video_vlc(app, path)
                self.current_player = 'vlc'
                print("Using VLC player")
                return
            except Exception as e:
                print(f"VLC failed: {e}")
        
        # Резервный вариант - OpenCV
        if OPENCV_AVAILABLE:
            try:
                play_video_opencv(app, path)
                self.current_player = 'opencv'
                print("Using OpenCV player (no audio)")
                return
            except Exception as e:
                print(f"OpenCV failed: {e}")
        
        # Все варианты не сработали
        self.show_error(app, "Не удалось воспроизвести видео")
    
    def stop_video(self, app):
        """Остановка текущего плеера"""
        if self.current_player == 'vlc' and VLC_AVAILABLE:
            stop_video_vlc(app)
        elif self.current_player == 'opencv' and OPENCV_AVAILABLE:
            stop_video_opencv(app)
        
        self.current_player = None
    
    def show_error(self, app, message):
        """Показать сообщение об ошибке"""
        for widget in app.video_frame.winfo_children():
            widget.destroy()
        
        error_label = tk.Label(app.video_frame, text=message, fg='red', wraplength=300)
        error_label.pack(fill=tk.BOTH, expand=True)
        app.video_label = error_label

# Глобальный менеджер видео-плееров
video_manager = VideoPlayerManager()

def play_video(app, path):
    """Основная функция воспроизведения видео"""
    video_manager.play_video(app, path)

def stop_video(app):
    """Основная функция остановки видео"""
    video_manager.stop_video(app)