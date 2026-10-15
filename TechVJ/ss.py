import os
import time
import cv2
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto
from tempfile import mkdtemp
import humanize

MAX_SIZE = 1.9 * 1024 * 1024 * 1024  # 1.9 GB limit

async def download_progress(current, total, msg, start_time):
    percentage = current * 100 / total
    speed = current / (time.time() - start_time + 1e-6)
    eta = (total - current) / (speed + 1e-6)

    progress = f"📥 **Downloading:** {percentage:.2f}%\n"
    progress += f"🚀 **Speed:** {humanize.naturalsize(speed, binary=True)}/s\n"
    progress += f"⏳ **ETA:** {int(eta)}s"

    try:
        await msg.edit_text(progress)
    except:
        pass

async def take_screenshots(video_path, output_dir, count, msg):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        raise ValueError("Could not read video frames.")
        
    interval = total_frames // count
    if interval < 1:
        interval = 1
        
    screenshots = []

    for i in range(min(count, total_frames)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i * interval)
        success, frame = cap.read()
        if success:
            path = os.path.join(output_dir, f"ss_{i+1}.jpg")
            cv2.imwrite(path, frame)
            screenshots.append(path)
            try:
                await msg.edit_text(f"📸 **Taking screenshots:** {i+1}/{count}")
            except:
                pass

    cap.release()
    return screenshots

@Client.on_message(filters.command(["ss"]) & filters.private)
async def generate_screenshots_command(client: Client, message: Message):
    target_message = message.reply_to_message if message.reply_to_message else message
    
    media = target_message.video or target_message.document
    if not media:
        await message.reply_text("❌ Please reply to a video or document with `/ss`.")
        return

    file_size = media.file_size
    if file_size > MAX_SIZE:
        await message.reply_text("❌ File too large. Limit is 1.9 GB.")
        return

    temp_dir = mkdtemp()
    file_path = os.path.join(temp_dir, "video.mp4")

    msg = await message.reply_text("📥 Starting download...")
    start_time = time.time()

    try:
        await target_message.download(
            file_path,
            progress=download_progress,
            progress_args=(msg, start_time)
        )
    except Exception as e:
        await msg.edit_text(f"❌ Download failed: `{e}`")
        return

    await msg.edit_text("📸 Starting screenshot generation...")
    try:
        # Reduced to 10 screenshots to avoid massive media album spam / FloodWaits
        screenshots = await take_screenshots(file_path, temp_dir, 10, msg)
    except Exception as e:
        await msg.edit_text(f"❌ Error processing video: `{e}`")
        return

    await msg.edit_text("📤 Uploading screenshots album...")

    try:
        # Group photos into media groups (Telegram allows up to 10 media per album)
        media_group = [InputMediaPhoto(media=path) for path in screenshots if os.path.exists(path)]
        
        if media_group:
            await client.send_media_group(
                chat_id=message.chat.id,
                media=media_group,
                reply_to_message_id=target_message.id
            )
        
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Upload failed due to flood limit or error: `{e}`")

    # Clean up temporary directory and files
    try:
        for file in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, file))
        os.rmdir(temp_dir)
    except Exception:
        pass
    
