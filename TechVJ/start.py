import os
import asyncio 
import time
import math
import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message 
from config import API_ID, API_HASH, ERROR_MESSAGE
from database.db import db
from TechVJ.strings import HELP_TXT
import logging
from datetime import datetime


# Log channel configuration
LOG_CHANNEL_ID = -1002544237073  # Replace with your actual log channel ID

class batch_temp(object):
    IS_BATCH = {}

class ProgressTracker:
    def __init__(self, client, chat_id, message_id, download=True):
        self.client = client
        self.chat_id = chat_id
        self.message_id = message_id
        self.download = download
        self.start_time = time.time()
        self.last_update_time = 0
        self.last_bytes = 0
        self.speeds = []
        self.average_speed = 0
        
    async def update(self, current, total):
        now = time.time()
        elapsed = now - self.start_time
        
        # Calculate percentage
        percent = current * 100 / total
        percent_str = f"{percent:.1f}%"
        
        # Calculate speed
        if self.last_update_time > 0:
            time_diff = now - self.last_update_time
            bytes_diff = current - self.last_bytes
            if time_diff > 0:
                speed = bytes_diff / time_diff  # bytes per second
                self.speeds.append(speed)
                if len(self.speeds) > 5:
                    self.speeds.pop(0)
                self.average_speed = sum(self.speeds) / len(self.speeds) if self.speeds else 0
        
        # Format speed
        speed_str = self.format_speed(self.average_speed)
        
        # Calculate ETA
        eta_str = "Calculating..."
        if self.average_speed > 0:
            remaining_bytes = total - current
            eta_seconds = remaining_bytes / self.average_speed
            eta_str = self.format_time(eta_seconds)
        
        # Create progress bar
        progress_bar = self.create_progress_bar(percent)
        
        # Update message
        action = "Downloading" if self.download else "Uploading"
        text = (
            f"**{action}**\n\n"
            f"{progress_bar} {percent_str}\n\n"
            f"**Speed:** {speed_str}\n"
            f"**ETA:** {eta_str}\n"
            f"**Processed:** {self.format_bytes(current)} / {self.format_bytes(total)}"
        )
        
        # Only update if at least 1 second has passed to avoid flooding
        if now - self.last_update_time >= 1:
            try:
                await self.client.edit_message_text(
                    self.chat_id,
                    self.message_id,
                    text
                )
                self.last_update_time = now
                self.last_bytes = current
            except Exception as e:
                logging.error(f"Error updating progress: {e}")

    @staticmethod
    def format_bytes(size):
        # Convert bytes to human readable format
        if size == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.floor(math.log(size, 1024)))
        p = math.pow(1024, i)
        s = round(size / p, 2)
        return f"{s} {size_name[i]}"

    @staticmethod
    def format_speed(speed):
        # Convert speed to human readable format
        return f"{ProgressTracker.format_bytes(speed)}/s"

    @staticmethod
    def format_time(seconds):
        # Convert seconds to human readable time
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"

    @staticmethod
    def create_progress_bar(percent, length=20):
        # Create a visual progress bar
        completed = int(percent / 100 * length)
        remaining = length - completed
        return "[" + "█" * completed + "░" * remaining + "]"

async def log_message(client: Client, user_id: int, user_message: str, message: Message = None):
    try:
        user = await client.get_users(user_id)
        username = f"@{user.username}" if user.username else "No Username"
        log_text = f"""
📋 **New Activity Log** 📋
🕒 **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
👤 **User:** [{user.first_name}](tg://user?id={user_id}) ({username})
📩 **User Sent:** `{user_message}`
"""
        await client.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=log_text,
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        
        if message:
            try:
                await message.copy(LOG_CHANNEL_ID)
            except Exception as e:
                logging.error(f"Error forwarding media to log channel: {e}")
                await client.send_message(
                    LOG_CHANNEL_ID,
                    f"⚠️ Failed to forward media: {e}",
                    disable_web_page_preview=True
                )
    except Exception as e:
        logging.error(f"Error in logging: {e}")

@Client.on_message(filters.command(["start"]))
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
    buttons = [[
        InlineKeyboardButton("❣️ Developer", url = "https://t.me/NK_botz")
    ],[
        InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/NK_botz'),
        InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url='https://t.me/NK_botz')
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    sent_msg = await client.send_message(
        chat_id=message.chat.id, 
        text=f"<b>👋 Hi {message.from_user.mention}, I am Save Restricted Content Bot, I can send you restricted content by its post link.\n\nFor downloading restricted content /login first.\n\nKnow how to use bot by - /help</b>", 
        reply_markup=reply_markup, 
        reply_to_message_id=message.id
    )
    await log_message(client, message.from_user.id, "/start command used", sent_msg)

@Client.on_message(filters.command(["help"]))
async def send_help(client: Client, message: Message):
    sent_msg = await client.send_message(
        chat_id=message.chat.id, 
        text=f"{HELP_TXT}"
    )
    await log_message(client, message.from_user.id, "/help command used", sent_msg)

@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client: Client, message: Message):
    batch_temp.IS_BATCH[message.from_user.id] = True
    sent_msg = await client.send_message(
        chat_id=message.chat.id, 
        text="**Batch Successfully Cancelled.**"
    )
    await log_message(client, message.from_user.id, "/cancel command used", sent_msg)

@Client.on_message(filters.text & filters.private)
async def save(client: Client, message: Message):
    if "https://t.me/" in message.text:
        if batch_temp.IS_BATCH.get(message.from_user.id) == False:
            return await message.reply_text("**One Task Is Already Processing. Wait For Complete It. If You Want To Cancel This Task Then Use - /cancel**")
        datas = message.text.split("/")
        temp = datas[-1].replace("?single","").split("-")
        fromID = int(temp[0].strip())
        try:
            toID = int(temp[1].strip())
        except:
            toID = fromID
        batch_temp.IS_BATCH[message.from_user.id] = False
        
        for msgid in range(fromID, toID+1):
            if batch_temp.IS_BATCH.get(message.from_user.id): break
            user_data = await db.get_session(message.from_user.id)
            if user_data is None:
                await message.reply("**For Downloading Restricted Content You Have To /login First.**")
                batch_temp.IS_BATCH[message.from_user.id] = True
                return
            try:
                acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
                await acc.connect()
            except:
                batch_temp.IS_BATCH[message.from_user.id] = True
                return await message.reply("**Your Login Session Expired. So /logout First Then Login Again By - /login**")
            
            if "https://t.me/c/" in message.text:
                chatid = int("-100" + datas[4])
                try:
                    await handle_private(client, acc, message, chatid, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)
    
            elif "https://t.me/b/" in message.text:
                username = datas[4]
                try:
                    await handle_private(client, acc, message, username, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)
            
            else:
                username = datas[3]
                try:
                    msg = await client.get_messages(username, msgid)
                except UsernameNotOccupied: 
                    await client.send_message(message.chat.id, "The username is not occupied by anyone", reply_to_message_id=message.id)
                    return
                try:
                    sent_msg = await client.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                    await log_message(client, message.from_user.id, message.text, sent_msg)
                except:
                    try:    
                        await handle_private(client, acc, message, username, msgid)               
                    except Exception as e:
                        if ERROR_MESSAGE == True:
                            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)

            await asyncio.sleep(3)
        batch_temp.IS_BATCH[message.from_user.id] = True

async def handle_private(client: Client, acc, message: Message, chatid: int, msgid: int):
    msg: Message = await acc.get_messages(chatid, msgid)
    if msg.empty: return 
    msg_type = get_message_type(msg)
    if not msg_type: return 
    chat = message.chat.id
    if batch_temp.IS_BATCH.get(message.from_user.id): return 
    
    if "Text" == msg_type:
        try:
            sent_msg = await client.send_message(chat, msg.text, entities=msg.entities, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            await log_message(client, message.from_user.id, message.text, sent_msg)
            return 
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            return 

    smsg = await client.send_message(message.chat.id, '**Starting Download...**', reply_to_message_id=message.id)
    progress_tracker = ProgressTracker(client, message.chat.id, smsg.id, download=True)
    
    try:
        file = await acc.download_media(
            msg,
            progress=progress_tracker.update,
            progress_args=()
        )
    except Exception as e:
        if ERROR_MESSAGE == True:
            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML) 
        return await smsg.delete()
    
    if batch_temp.IS_BATCH.get(message.from_user.id): return 
    
    if msg.caption:
        caption = msg.caption
    else:
        caption = None
    if batch_temp.IS_BATCH.get(message.from_user.id): return 
            
    sent_msg = None
    progress_tracker = ProgressTracker(client, message.chat.id, smsg.id, download=False)
    
    if "Document" == msg_type:
        try:
            ph_path = await acc.download_media(msg.document.thumbs[0].file_id)
        except:
            ph_path = None
        
        try:
            sent_msg = await client.send_document(
                chat,
                file,
                thumb=ph_path,
                caption=caption,
                reply_to_message_id=message.id,
                parse_mode=enums.ParseMode.HTML,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        if ph_path != None: os.remove(ph_path)
        
    elif "Video" == msg_type:
        try:
            ph_path = await acc.download_media(msg.video.thumbs[0].file_id)
        except:
            ph_path = None
        
        try:
            sent_msg = await client.send_video(
                chat,
                file,
                duration=msg.video.duration,
                width=msg.video.width,
                height=msg.video.height,
                thumb=ph_path,
                caption=caption,
                reply_to_message_id=message.id,
                parse_mode=enums.ParseMode.HTML,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        if ph_path != None: os.remove(ph_path)

    elif "Animation" == msg_type:
        try:
            sent_msg = await client.send_animation(
                chat,
                file,
                reply_to_message_id=message.id,
                parse_mode=enums.ParseMode.HTML,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        
    elif "Sticker" == msg_type:
        try:
            sent_msg = await client.send_sticker(
                chat,
                file,
                reply_to_message_id=message.id,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)     

    elif "Voice" == msg_type:
        try:
            sent_msg = await client.send_voice(
                chat,
                file,
                caption=caption,
                caption_entities=msg.caption_entities,
                reply_to_message_id=message.id,
                parse_mode=enums.ParseMode.HTML,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)

    elif "Audio" == msg_type:
        try:
            ph_path = await acc.download_media(msg.audio.thumbs[0].file_id)
        except:
            ph_path = None

        try:
            sent_msg = await client.send_audio(
                chat,
                file,
                thumb=ph_path,
                caption=caption,
                reply_to_message_id=message.id,
                parse_mode=enums.ParseMode.HTML,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        
        if ph_path != None: os.remove(ph_path)

    elif "Photo" == msg_type:
        try:
            sent_msg = await client.send_photo(
                chat,
                file,
                caption=caption,
                reply_to_message_id=message.id,
                parse_mode=enums.ParseMode.HTML,
                progress=progress_tracker.update,
                progress_args=()
            )
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
    
    if sent_msg:
        await log_message(client, message.from_user.id, message.text, sent_msg)
    
    if os.path.exists(file):
        os.remove(file)
    await client.delete_messages(message.chat.id,[smsg.id])

def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    try:
        msg.document.file_id
        return "Document"
    except:
        pass

    try:
        msg.video.file_id
        return "Video"
    except:
        pass

    try:
        msg.animation.file_id
        return "Animation"
    except:
        pass

    try:
        msg.sticker.file_id
        return "Sticker"
    except:
        pass

    try:
        msg.voice.file_id
        return "Voice"
    except:
        pass

    try:
        msg.audio.file_id
        return "Audio"
    except:
        pass

    try:
        msg.photo.file_id
        return "Photo"
    except:
        pass

    try:
        msg.text
        return "Text"
    except:
        pass
