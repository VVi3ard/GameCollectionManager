import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import json
from pathlib import Path
import concurrent.futures
import queue
import uuid
import shutil
import threading


def resolve_ffmpeg_binaries():
    app_dir = Path(__file__).resolve().parent
    local_bin_dir = app_dir / "ffmpeg" / "bin"
    local_ffmpeg = local_bin_dir / "ffmpeg.exe"
    local_ffprobe = local_bin_dir / "ffprobe.exe"

    if local_ffmpeg.exists() and local_ffprobe.exists():
        return str(local_ffmpeg), str(local_ffprobe)

    return "ffmpeg", "ffprobe"

def compress_video_file(input_path, scale_factor, crf_value, max_duration):
    try:
        input_path = os.path.normpath(input_path)
        ffmpeg_bin, ffprobe_bin = resolve_ffmpeg_binaries()
        
        if 'backup' in input_path.split(os.sep):
            raise Exception("Попытка обработки файла в папке backup")
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Файл не существует: {input_path}")
        
        print(f"Сжатие: {os.path.basename(input_path)}")
        
        file_dir = os.path.dirname(input_path)
        backup_dir = os.path.join(file_dir, "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        filename = os.path.basename(input_path)
        backup_path = os.path.join(backup_dir, filename)
        
        if not os.path.exists(backup_path):
            shutil.copy2(input_path, backup_path)
            print(f"Создан backup: {backup_path}")
        else:
            print(f"Используем существующий backup")
        
        temp_id = uuid.uuid4().hex[:8]
        output_path = f"{input_path}.{temp_id}.temp.mp4"
        output_path = os.path.normpath(output_path)
        
        cmd_info = [
            ffprobe_bin, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", input_path
        ]
        
        result = subprocess.run(cmd_info, capture_output=True, text=True)
        
        if result.returncode != 0:
            duration = 10.0
            width, height = 640, 480
            print("Используем значения по умолчанию")
        else:
            info = json.loads(result.stdout)
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            if not video_stream:
                raise Exception("Видео поток не найден")
            
            duration = float(info['format']['duration'])
            width = int(video_stream['width'])
            height = int(video_stream['height'])
        
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        min_height = 240
        if new_height < min_height:
            new_width = width
            new_height = height
       
        new_width = new_width // 2 * 2
        new_height = new_height // 2 * 2
        
        cmd = [
            ffmpeg_bin,
            "-i", input_path, 
            "-y",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", str(crf_value),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={new_width}:{new_height}:flags=lanczos",
            "-profile:v", "high",
            "-level", "4.0",
            "-tune", "film",
            "-x264opts", "merange=24:b-adapt=2",
            "-c:a", "aac",
            "-b:a", "64k",
            "-ac", "2",
            "-ar", "48000",
            "-profile:a", "aac_low",
            "-movflags", "+faststart",
            "-threads", "2",
            output_path
        ]
        
        if duration > max_duration:
            start_time = max(0, (duration - max_duration) / 2)
            cmd = cmd[:1] + ["-ss", str(start_time), "-t", str(max_duration)] + cmd[1:]
        
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if process.returncode != 0:
            raise Exception(f"Ошибка FFmpeg: {process.stderr}")
        
        if not os.path.exists(output_path):
            raise Exception("Выходной файл не создан после сжатия")
        
        if os.path.getsize(output_path) == 0:
            raise Exception("Выходной файл пустой")
        
        shutil.move(output_path, input_path)
        
        print(f"Успешно сжато: {os.path.basename(input_path)}")
        return True
        
    except Exception as e:
        print(f"Ошибка при сжатии {input_path}: {e}")
        
        if 'backup_path' in locals() and os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, input_path)
                print(f"Восстановлен оригинал из backup")
            except Exception as restore_error:
                print(f"Ошибка восстановления: {restore_error}")
        
        if 'output_path' in locals() and output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        raise

def compress_video(app, collection_dir, collection_label):
    if not collection_dir:
        messagebox.showinfo("Информация", "Сначала выберите каталог экспорта")
        return

    if not os.path.exists(collection_dir):
        messagebox.showerror("Ошибка", f"Каталог не найден: {collection_dir}")
        return

    compression_dialog = tk.Toplevel(app.root)
    compression_dialog.title(f"Сжатие видео: {collection_label}")
    compression_dialog.geometry("500x450")
    
    ttk.Label(
        compression_dialog,
        text=f"Настройки сжатия видео\n{collection_label}",
        font=("Arial", 12, "bold")
    ).pack(pady=10)
    
    scale_var = tk.DoubleVar(value=0.75)
    crf_var = tk.IntVar(value=27)
    max_duration_var = tk.IntVar(value=10)
    parallel_var = tk.IntVar(value=6)
    
    settings_frame = ttk.Frame(compression_dialog)
    settings_frame.pack(pady=10, padx=20, fill=tk.X)
    
    ttk.Label(settings_frame, text="Масштаб (0.1-1.0):").grid(row=0, column=0, sticky=tk.W, pady=5)
    scale_scale = ttk.Scale(settings_frame, from_=0.1, to=1.0, variable=scale_var, orient=tk.HORIZONTAL)
    scale_scale.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
    ttk.Label(settings_frame, textvariable=scale_var).grid(row=0, column=2, padx=5)
    
    ttk.Label(settings_frame, text="Качество (CRF 0-51):").grid(row=1, column=0, sticky=tk.W, pady=5)
    crf_scale = ttk.Scale(settings_frame, from_=0, to=51, variable=crf_var, orient=tk.HORIZONTAL)
    crf_scale.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
    ttk.Label(settings_frame, textvariable=crf_var).grid(row=1, column=2, padx=5)
    
    crf_info_text = tk.StringVar()
    crf_info_text.set("27 - хорошее качество (по умолчанию)")
    
    def update_crf_info(*args):
        crf_value = crf_var.get()
        if crf_value <= 18:
            crf_info_text.set("18-23 - отличное качество")
        elif crf_value <= 27:
            crf_info_text.set("23-27 - хорошее качество")
        elif crf_value <= 35:
            crf_info_text.set("28-35 - среднее качество")
        else:
            crf_info_text.set("36-51 - низкое качество")
    
    crf_var.trace('w', update_crf_info)
    ttk.Label(settings_frame, textvariable=crf_info_text, font=("Arial", 8)).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=2)
    
    ttk.Label(settings_frame, text="Макс. длительность (сек):").grid(row=3, column=0, sticky=tk.W, pady=5)
    duration_spin = ttk.Spinbox(settings_frame, from_=5, to=60, textvariable=max_duration_var, width=10)
    duration_spin.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
    
    ttk.Label(settings_frame, text="Параллельных задач:").grid(row=4, column=0, sticky=tk.W, pady=5)
    parallel_spin = ttk.Spinbox(settings_frame, from_=1, to=12, textvariable=parallel_var, width=10)
    parallel_spin.grid(row=4, column=1, sticky=tk.W, pady=5, padx=5)
    
    settings_frame.columnconfigure(1, weight=1)
    
    status_var = tk.StringVar(value="Готов к обработке")
    status_label = ttk.Label(compression_dialog, textvariable=status_var)
    status_label.pack(pady=10)

    ttk.Label(
        compression_dialog,
        text=f"Каталог: {collection_dir}",
        wraplength=440,
        justify=tk.LEFT
    ).pack(padx=20, anchor=tk.W)
    
    progress = ttk.Progressbar(compression_dialog, mode="determinate")
    progress.pack(fill=tk.X, padx=20, pady=5)
    
    parallel_frame = ttk.Frame(compression_dialog)
    parallel_frame.pack(fill=tk.X, padx=20, pady=5)
    
    ttk.Label(parallel_frame, text="Активные задачи:").pack(anchor=tk.W)
    active_tasks_var = tk.StringVar(value="0/0")
    active_label = ttk.Label(parallel_frame, textvariable=active_tasks_var)
    active_label.pack(anchor=tk.W)
    
    def start_compression():
        video_files = []
        media_dir = os.path.join(collection_dir, "media")
        
        for root, dirs, files in os.walk(media_dir):
            if 'backup' in dirs:
                dirs.remove('backup')
            for file in files:
                if file.lower().endswith('.mp4'):
                    full_path = os.path.join(root, file)
                    video_files.append((file, full_path))
        
        if not video_files:
            status_var.set("MP4 файлы не найдены в media/")
            return
        
        total_files = len(video_files)
        progress["maximum"] = total_files
        progress["value"] = 0
        
        max_workers = parallel_var.get()
        
        def compress_worker():
            completed_count = 0
            task_queue = queue.Queue()
            
            for video_file in video_files:
                task_queue.put(video_file)
            
            def worker_task(file_info):
                filename, full_path = file_info
                try:
                    status_var.set(f"Обработка: {filename}")
                    result = compress_video_file(
                        full_path, 
                        scale_var.get(),
                        crf_var.get(),
                        max_duration_var.get()
                    )
                    return (filename, result, None)
                except Exception as e:
                    return (filename, False, str(e))
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                active_tasks = 0
                
                def update_status():
                    active_tasks_var.set(f"{active_tasks}/{max_workers}")
                    compression_dialog.update_idletasks()
                
                for _ in range(min(max_workers, task_queue.qsize())):
                    if not task_queue.empty():
                        file_info = task_queue.get()
                        future = executor.submit(worker_task, file_info)
                        futures[future] = file_info
                        active_tasks += 1
                        update_status()
                
                while futures:
                    done, _ = concurrent.futures.wait(futures.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
                    
                    for future in done:
                        file_info = futures.pop(future)
                        filename, success, error = future.result()
                        
                        completed_count += 1
                        progress["value"] = completed_count
                        
                        if error:
                            print(f"Ошибка сжатия {filename}: {error}")
                        else:
                            print(f"Успешно: {filename}")
                        
                        if not task_queue.empty():
                            new_file_info = task_queue.get()
                            new_future = executor.submit(worker_task, new_file_info)
                            futures[new_future] = new_file_info
                        else:
                            active_tasks -= 1
                        
                        update_status()
                        compression_dialog.update_idletasks()
                
            status_var.set("Обработка завершена!")
            messagebox.showinfo("Готово", f"Сжатие видео завершено\nОбработано: {completed_count}/{total_files}")
        
        threading.Thread(target=compress_worker, daemon=True).start()
    
    btn_frame = ttk.Frame(compression_dialog)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text="Начать сжатие", command=start_compression).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Отмена", command=compression_dialog.destroy).pack(side=tk.LEFT, padx=5)
