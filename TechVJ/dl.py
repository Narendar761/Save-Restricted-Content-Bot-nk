import os
import time
import glob
import logging
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp

logger = logging.getLogger(__name__)

def get_progress_bar(percentage):
    """Generates a clean visual block progress bar."""
    completed_blocks = int(percentage / 10)
    remaining_blocks = 10 - completed_blocks
    return "🔹" * completed_blocks + "🔸" * remaining_blocks

def format_bytes(size):
    """Formats bytes into human readable units."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

async def progress_callback(current, total, status_message, action_text, start_time):
    """Tracks dynamic updates, including speeds, ETA, and a visual progress bar."""
    now = time.time()
    elapsed_time = now - start_time
    if elapsed_time <= 0:
        return

    percentage = (current / total) * 100
    speed = current / elapsed_time
    eta = (total - current) / speed if speed > 0 else 0

    readable_speed = format_bytes(speed)
    readable_eta = time.strftime("%H:%M:%S", time.gmtime(eta))
    progress_bar = get_progress_bar(percentage)

    if int(percentage) % 10 == 0 or current == total:
        try:
            await status_message.edit_text(
                f"📊 **{action_text}**\n\n"
                f"{progress_bar} `{percentage:.1f}%`\n\n"
                f"**Processed:** {format_bytes(current)} / {format_bytes(total)}\n"
                f"**Speed:** {readable_speed}/s\n"
                f"**ETA:** {readable_eta}"
            )
        except Exception:
            pass

def generate_screenshot(video_path, thumb_path):
    """Fallback function to capture a screenshot using FFmpeg at the 2-second mark."""
    try:
        command = [
            "ffmpeg", "-y",
            "-ss", "00:00:02",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            thumb_path
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return os.path.exists(thumb_path)
    except Exception as e:
        logger.error(f"FFmpeg screenshot generation failed: {e}")
        return False

@Client.on_message(filters.command(["dl"]) & filters.private)
async def download_video_link(client: Client, message: Message):
    # Extract URL from command arguments e.g., "/dl https://youtube.com/..."
    if len(message.command) < 2:
        await message.reply_text("❌ Please provide a link after /dl command.\nExample: `/dl https://youtu.be/xyz`")
        return

    url = message.command[1].strip()
    if not url.startswith(("http://", "https://")):
        await message.reply_text("❌ Please send a valid HTTP/HTTPS URL.")
        return

    status_message = await message.reply_text("📥 Analyzing link and starting download...")
    download_dir = f"downloads/{message.chat.id}_{message.id}"
    os.makedirs(download_dir, exist_ok=True)

    def ytdl_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('max_filesize') or d.get('total_bytes_estimate') or 1
            current = d.get('downloaded_bytes', 0)
            percentage = (current / total) * 100
            
            speed = d.get('speed') or 0
            eta = d.get('eta') or 0
            
            readable_speed = format_bytes(speed) if speed else "Calculating..."
            readable_eta = time.strftime("%H:%M:%S", time.gmtime(eta)) if eta else "Calculating..."
            progress_bar = get_progress_bar(percentage)

            if int(percentage) % 10 == 0:
                try:
                    asyncio.run_coroutine_threadsafe(
                        status_message.edit_text(
                            f"📥 **Downloading Video File**\n\n"
                            f"{progress_bar} `{percentage:.1f}%`\n\n"
                            f"**Processed:** {format_bytes(current)} / {format_bytes(total)}\n"
                            f"**Speed:** {readable_speed}/s\n"
                            f"**ETA:** {readable_eta}"
                        ),
                        client.loop
                    )
                except Exception:
                    pass

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{download_dir}/%(id)s.%(ext)s',
        'restrictfilenames': True,
        'writethumbnail': True,
        'quiet': True,
        'progress_hooks': [ytdl_hook],
        'compat_options': ['allow-unsafe-ext'],
    }

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = client.loop

        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info), info.get('title', 'Video File')

        filename, title = await loop.run_in_executor(None, download)

        if not os.path.exists(filename):
            matched_files = glob.glob(f"{download_dir}/*")
            video_files = [f for f in matched_files if not f.lower().endswith(('.jpg', '.jpeg', '.webp', '.png'))]
            if video_files:
                filename = video_files[0]
            else:
                raise FileNotFoundError("Target download file could not be mapped locally.")

        file_size = os.path.getsize(filename)
        if file_size > 2000 * 1024 * 1024:
            await status_message.edit_text("❌ Downloaded file exceeds Telegram's maximum 2 GB upload limit.")
            return

        await status_message.edit_text("🖼️ Processing media thumbnail assets...")

        thumb_file = None
        base_name = os.path.splitext(filename)[0]
        possible_thumbs = glob.glob(f"{base_name}.*")
        
        for f in possible_thumbs:
            if f.lower().endswith(('.jpg', '.jpeg', '.webp', '.png')):
                thumb_file = f
                break

        if not thumb_file or not os.path.exists(thumb_file):
            fallback_thumb = f"{download_dir}/thumb_{message.id}.jpg"
            success = await loop.run_in_executor(None, generate_screenshot, filename, fallback_thumb)
            if success:
                thumb_file = fallback_thumb

        await status_message.edit_text("📤 Uploading media via MTProto layer...")
        
        upload_start_time = time.time()
        await message.reply_video(
            video=filename,
            caption=f"🎥 **{title}**",
            thumb=thumb_file if thumb_file and os.path.exists(thumb_file) else None,
            progress=progress_callback,
            progress_args=(status_message, "Uploading file to Telegram", upload_start_time)
        )
        
        await status_message.delete()

    except Exception as e:
        logger.error(f"Execution Error: {e}")
        await status_message.edit_text(f"❌ Operation failed.\n**Reason:** `{str(e)}`")
        
    finally:
        if os.path.exists(download_dir):
            for file in glob.glob(f"{download_dir}/*"):
                try:
                    os.remove(file)
                except Exception:
                    pass
            try:
                os.rmdir(download_dir)
            except Exception:
                pass
                
