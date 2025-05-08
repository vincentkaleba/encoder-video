import asyncio
import json
import os
import re
import shutil
import time
from typing import Dict
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageIdInvalid
from bot import Dependencies
from utils.videoclient import AudioCodec, AudioTrack, MediaType, VideoClient
from utils.helper import convert_to_seconds, progress_for_pyrogram, convert_to_seconds, seconds_to_timestamp
from pathlib import Path
import humanize

deps = Dependencies()
users_operations: Dict[int, dict] = {}
SUPPORTED_MIME_TYPES = {
    'video/mp4', 'video/quicktime', 'video/x-matroska', 'video/webm', 'audio/mpeg',
    'video/x-msvideo', 'video/x-flv', 'video/3gpp', 'video/x-ms-wmv'
}
SUPPORTED_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.webm', '.mp3', '.avi', '.flv', '.3gp', '.wmv'}

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗜 Compresser", callback_data="compress"),
            InlineKeyboardButton("✂️ Supprimer Scene", callback_data="cut")
        ],
        [
            InlineKeyboardButton("📹 Vidéo", callback_data="video_menu1"),
            InlineKeyboardButton("🔄 Convertir", callback_data="convert")
        ],
        [
            InlineKeyboardButton("🎵 Audio", callback_data="audio_menu1"),
            InlineKeyboardButton("📝 Sous-titres", callback_data="subs_menu1")
        ],
        [
            InlineKeyboardButton("📌 Chapitres", callback_data="tools_menu1"),
            InlineKeyboardButton("ℹ️ Infos", callback_data="info_menu")
        ],
        [
            InlineKeyboardButton("⚙️ Paramètres", callback_data="settings"),
            InlineKeyboardButton("❌ Fermer", callback_data="close")
        ]
    ])

def video_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔀 Fusion Vidéo", callback_data="video_merge"),
            InlineKeyboardButton("✂️ Découpage", callback_data="video_split")
        ],
        [
            InlineKeyboardButton("📏 Tronquer", callback_data="video_trim"),
            InlineKeyboardButton("✂️ Supprimer Scene", callback_data="cut")
        ],
        [
            InlineKeyboardButton("🗜 Compression", callback_data="compress"),
            InlineKeyboardButton("🖼 Miniature", callback_data="generate_thumbnail")
        ],
        [
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def audio_menu1():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Extraire Audio", callback_data="audio_extract"),
            InlineKeyboardButton("🔊 Sélection Audio", callback_data="audio_selection")
        ],
        [
            InlineKeyboardButton("🔄 Convertir en Audio", callback_data="convert_audio"),
            InlineKeyboardButton("🔇 Supprimer Audio", callback_data="remove_audio")
        ],
        [
            InlineKeyboardButton("🎼 Fusion Vidéo/Audio", callback_data="merge_video_audio"),
            InlineKeyboardButton("🌐 Langue Audio", callback_data="audio_language")
        ],
        [
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def subs_menu1():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Ajouter Sous-titres", callback_data="subtitle_add"),
            InlineKeyboardButton("📤 Extraire Sous-titres", callback_data="subtitle_extract")
        ],
        [
            InlineKeyboardButton("👁 Sélection Sous-titres", callback_data="choose_subtitle"),
            InlineKeyboardButton("🗑 Supprimer Sous-titres", callback_data="remove_subtitles")
        ],
        [
            InlineKeyboardButton("🌐 Sous-titres permanents", callback_data="choose_subtitle_burn"),
            InlineKeyboardButton("🏷 Forcer Sous-titres", callback_data="force_subtitle")
        ],
        [
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def tools_menu1():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Ajouter Chapitres", callback_data="add_chapters"),
            InlineKeyboardButton("✏️ Modifier Chapitre", callback_data="edit_chapter")
        ],
        [
            InlineKeyboardButton("✂️ Diviser Chapitre", callback_data="split_chapter"),
            InlineKeyboardButton("🗑 Supprimer Chapitres", callback_data="remove_chapters")
        ],
        [
            InlineKeyboardButton("📋 Lister Chapitres", callback_data="get_chapters"),
            InlineKeyboardButton("🔍 Voir Chapitre", callback_data="get_chapter")
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="main_menu")]
    ])

def info_menu():
    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton("📊 All Infos", callback_data="all_info"),
            InlineKeyboardButton("� Retour", callback_data="main_menu")
        ]
    ])

@Client.on_message(filters.document | filters.video | filters.audio & filters.private)
async def handle_video(client: Client, message: Message):
    file_type = None
    file_name = None
    
    if message.video:
        file_type = "video"
        file_name = message.video.file_name or f"video_{message.id}.mp4"
    elif message.document:
        file_name = message.document.file_name
        if not file_name:
            await message.reply_text("❌ Impossible de déterminer le type de fichier")
            return
            
        ext = Path(file_name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            await message.reply_text(f"❌ Format non supporté: {ext}")
            return
            
        mime_type = message.document.mime_type
        if mime_type not in SUPPORTED_MIME_TYPES:
            await message.reply_text(f"❌ Type MIME non supporté: {mime_type}")
            return
            
        file_type = "video" if "video" in mime_type else "audio"
    elif message.audio:
        file_type = "audio"
        file_name = message.audio.file_name or f"audio_{message.id}.mp3"
    
    if file_name:
        ext = Path(file_name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            await message.reply_text(f"❌ Extension non supportée: {ext}")
            return
        
    await message.reply_text(
        "🔧 Sélectionnez une opération :",
        reply_markup=main_menu(),
        parse_mode=ParseMode.HTML,
        reply_to_message_id=message.id
    )

@Client.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user = callback_query.from_user
    msg = callback_query.message
    me = await client.get_me()
    if data == "main_menu":
        await callback_query.edit_message_text(
            "🔧 Sélectionnez une opération :",
            reply_markup=main_menu()
        )
    elif data == "video_menu1":
        await callback_query.edit_message_text(
            "📹 Menu Vidéo :",
            reply_markup=video_menu()
        )
    elif data == "audio_menu1":
        await callback_query.edit_message_text(
            "🔊 Menu Audio :",
            reply_markup=audio_menu1()
        )
    elif data == "subs_menu1":
        await callback_query.edit_message_text(
            "📝 Menu Sous-titres :",
            reply_markup=subs_menu1()
        )
    elif data == "tools_menu1":
        await callback_query.edit_message_text(
            "🛠 Outils avancés :",
            reply_markup=tools_menu1()
        )
    elif data == "info_menu":
        await callback_query.edit_message_text(
            "ℹ️ Informations :",
            reply_markup=info_menu()
        )
    elif data == "compress":
        if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
            await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
            return

        await callback_query.answer("⏳ Compression en préparation...", show_alert=False)
        
        user_dir = f"downloads/{user.id}_{int(time.time())}"
        os.makedirs(user_dir, exist_ok=True)
        
        try:
            status_msg = await msg.edit("⏳ Téléchargement en cours...")
        except MessageIdInvalid:
            status_msg = await msg.reply("⏳ Téléchargement en cours...")
        
        try:
            original_filename = None
            if msg.reply_to_message.document:
                original_filename = msg.reply_to_message.document.file_name
            elif msg.reply_to_message.video:
                original_filename = msg.reply_to_message.video.file_name
            
            if original_filename:
                filename_without_ext = os.path.splitext(original_filename)[0]
                output_basename = filename_without_ext
                download_filename = f"{user_dir}/{filename_without_ext}_original{os.path.splitext(original_filename)[1] or '.mp4'}"
            else:
                output_basename = "compressed"
                download_filename = f"{user_dir}/original.mp4"
            
            file_path = await msg.reply_to_message.download(
                file_name=download_filename,
                progress=progress_for_pyrogram,
                progress_args=("Téléchargement...", status_msg, time.time())
            )
        except Exception as e:
            await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
            try:
                os.rmdir(user_dir)
            except:
                pass
            return
        
        await status_msg.edit("⚙️ Compression en cours...")
        try:
            videoclient = deps.videoclient
            videoclient.output_path = Path(user_dir)
            
            try:
                media_info = await videoclient.get_media_info(file_path)
                width = media_info.width if media_info and hasattr(media_info, 'width') else 320
                height = media_info.height if media_info and hasattr(media_info, 'height') else None
                duration = int(media_info.duration) if media_info and hasattr(media_info, 'duration') else 0
            except Exception as e:
                print(f"⚠️ Erreur lors de la récupération des infos média: {str(e)}")
                width = 320
                height = None
                duration = 0
            
            result = await videoclient.compress_video(
                input_path=file_path,
                output_basename=output_basename,
                target_formats=["mp4"],
                keep_original_quality=False,
            )
            
            if "mp4" in result and result["mp4"]:
                for output_file in result["mp4"]:
                    if os.path.exists(output_file):
                        try:
                            await client.send_video(
                                chat_id=user.id,
                                video=output_file,
                                width=width,
                                height=height,
                                duration=duration,
                                caption=f"📦 Fichier compressé: {os.path.basename(output_file)}",
                                progress=progress_for_pyrogram,
                                progress_args=("Envoi...", status_msg, time.time())
                            )
                            await asyncio.sleep(1)
                        except Exception as send_error:
                            await status_msg.edit(f"❌ Erreur d'envoi: {str(send_error)}")
                            await client.send_message(
                                chat_id=user.id,
                                text=f"❌ Impossible d'envoyer la vidéo: {str(send_error)}"
                            )
                        finally:
                            try:
                                os.remove(output_file)
                            except Exception as clean_error:
                                print(f"Erreur de suppression du fichier: {str(clean_error)}")
            
            await status_msg.delete()
            
        except Exception as e:
            await status_msg.edit(f"❌ Erreur de compression: {str(e)}")
            await client.send_message(
                chat_id=user.id,
                text=f"❌ Échec de la compression: {str(e)}"
            )
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            for root, _, files in os.walk(user_dir):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except:
                        pass
            os.rmdir(user_dir)
        except Exception as e:
            print(f"Erreur de nettoyage: {str(e)}")


    elif data == "close":
        await callback_query.message.delete()
    
    elif data == "cut":
        try:
            await callback_query.answer("⏳ Découpage en préparation...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement en cours...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement en cours...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                if original_filename:
                    filename_without_ext = os.path.splitext(original_filename)[0]
                    download_filename = f"{user_dir}/{filename_without_ext}_original{os.path.splitext(original_filename)[1] or '.mp4'}"
                else:
                    download_filename = f"{user_dir}/original.mp4"
                
                file_path = await msg.reply_to_message.download(
                    file_name=download_filename,
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            cut_instructions = (
                "✂️ <b>Format attendu</b> : <code>HH:MM:SS-HH:MM:SS,HH:MM:SS-HH:MM:SS,...</code>\n\n"
                "Exemple :\n"
                "<code>00:01:30-00:02:45,00:03:00-00:04:15</code> pour deux séquences\n\n"
                "Envoyez maintenant les temps de découpage :"
            )
            
            cut_time_msg = await status_msg.edit(cut_instructions)
            
            try:
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=120
                )
                
                cut_ranges = []
                ranges = response.text.strip().split(",")
                
                for range_str in ranges:
                    if "-" not in range_str:
                        await status_msg.edit("❌ Format incorrect. Utilisez HH:MM:SS-HH:MM:SS,HH:MM:SS-HH:MM:SS,...")
                        return
                        
                    start_time, end_time = range_str.strip().split("-")
                    
                    def validate_time(time_str):
                        parts = time_str.split(":")
                        if len(parts) == 3:  # HH:MM:SS
                            return True
                        elif len(parts) == 2:  # MM:SS
                            return True
                        return False
                        
                    if not validate_time(start_time) or not validate_time(end_time):
                        await status_msg.edit("❌ Format de temps invalide")
                        return
                    
                    cut_ranges.append((convert_to_seconds(start_time), convert_to_seconds(end_time)))
                
                await response.delete()
                    
            except asyncio.TimeoutError:
                await status_msg.edit("❌ Temps écoulé (120s)")
                return
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
                return

            await status_msg.edit(f"✂️ Découpage de {len(cut_ranges)} plage(s)...")
            
            try:
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.cut_video(
                    input_path=file_path,
                    output_name="cut",
                    cut_ranges=cut_ranges, 
                )
                
                try:
                    result_media_info = await videoclient.get_media_info(result)
                    width = result_media_info.width if result_media_info and hasattr(result_media_info, 'width') else 320
                    height = result_media_info.height if result_media_info and hasattr(result_media_info, 'height') else None
                    duration = int(result_media_info.duration) if result_media_info and hasattr(result_media_info, 'duration') else 0
                except Exception as e:
                    print(f"⚠️ Erreur infos média résultat: {str(e)}")
                    width = 320
                    height = None
                    duration = 0
                
                if os.path.exists(result):
                    try:
                        await client.send_video(
                            chat_id=user.id,
                            video=result,
                            width=width,
                            height=height,
                            duration=duration,
                            caption=f"✂️ Vidéo découpée ({len(cut_ranges)} plage(s))",
                            progress=progress_for_pyrogram,
                            progress_args=("Envoi...", status_msg, time.time())
                        )
                        await asyncio.sleep(1)
                    except Exception as send_error:
                        await status_msg.edit(f"❌ Erreur d'envoi: {str(send_error)}")
                        await client.send_message(
                            chat_id=user.id,
                            text=f"❌ Impossible d'envoyer la vidéo: {str(send_error)}"
                        )
                    finally:
                        try:
                            os.remove(result)
                        except Exception as clean_error:
                            print(f"Erreur suppression fichier: {str(clean_error)}")
                
                await status_msg.delete()
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de découpage: {str(e)}")
                await client.send_message(
                    chat_id=user.id,
                    text=f"❌ Échec du découpage: {str(e)}"
                )
                
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur nettoyage: {str(e)}")
    
    elif data == "audio_extract":
        try:
            await callback_query.answer("⏳ Extraction audio en préparation...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement en cours...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement en cours...")
            
            try:
                file_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/original.mp4",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            try:
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                media_info = await videoclient.get_media_info(file_path)
                
                if not media_info.audio_tracks:
                    await status_msg.edit("❌ Aucune piste audio trouvée")
                    return
                    
                await status_msg.edit(f"🔊 {len(media_info.audio_tracks)} piste(s) audio détectée(s)...")
                
                LANGUAGE_NAMES = {
                    'jpn': "Japonais",
                    'eng': "Anglais",
                    'fre': "Français",
                    'spa': "Espagnol",
                    'ger': "Allemand",
                    'ita': "Italien",
                    # Ajouter d'autres langues au besoin
                }
                
                for track in media_info.audio_tracks:
                    file_name = f"piste_{track.index}_{track.language or 'unk'}"
                    
                    lang_name = LANGUAGE_NAMES.get(track.language, track.language or "Inconnu")
                    track_name = f"Piste {track.index} ({lang_name})"
                    
                    await status_msg.edit(f"⚙️ Extraction de {track_name}...")
                    
                    audio_path = await videoclient.extract_audio(
                        input_path=file_path,
                        output_name=file_name,
                        codec=track.codec if track.codec else AudioCodec.AAC,
                        bitrate=192
                    )
                    
                    if audio_path:
                        codec_name = str(track.codec).split('.')[-1] if track.codec else "AAC"
                        caption = (
                            f"🎧 {track_name}\n"
                            f"├ Codec: {codec_name}\n"
                            f"├ Canaux: {track.channels or 2}\n"
                            f"└ Piste par défaut: {'Oui' if track.is_default else 'Non'}"
                        )
                        
                        await client.send_audio(
                            chat_id=user.id,
                            audio=audio_path,
                            caption=caption,
                            title=f"Piste {track.index} - {lang_name}",
                            performer="Extraction audio",
                            progress=progress_for_pyrogram,
                            progress_args=(f"Envoi {track_name}...", status_msg, time.time())
                        )
                        
                        await asyncio.sleep(3)
                        
                        try:
                            os.remove(audio_path)
                        except:
                            pass
                
                await status_msg.edit("✅ Extraction terminée!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur nettoyage: {str(e)}")
    
    elif data == "all_info":
        try:
            await callback_query.answer("⏳ Récupération des informations...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier média trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement pour analyse...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement pour analyse...")
            
            try:
                file_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/temp_media",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            try:
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(file_path)
                
                LANGUAGE_NAMES = {
                    'jpn': "Japonais", 'eng': "Anglais", 'fre': "Français",
                    'spa': "Espagnol", 'ger': "Allemand", 'ita': "Italien"
                }
                

                media_type = str(media_info.media_type.value).upper()
                
                info_text = "📊 <b>INFORMATIONS MÉDIA</b>\n\n"
                info_text += f"📂 <b>Fichier</b>: <code>{os.path.basename(file_path)}</code>\n"
                info_text += f"📏 <b>Taille</b>: {humanize.naturalsize(media_info.size)}\n"
                info_text += f"⏱ <b>Durée</b>: {humanize.precisedelta(media_info.duration)}\n"
                info_text += f"🎞 <b>Format</b>: {media_type}\n"  
                
                if hasattr(media_info, 'width') and media_info.width:
                    info_text += f"🖼 <b>Résolution</b>: {media_info.width}x{media_info.height}\n"
                    if hasattr(media_info, 'bitrate') and media_info.bitrate:
                        info_text += f"📈 <b>Bitrate vidéo</b>: {media_info.bitrate} kbps\n"
                
                if media_info.audio_tracks:
                    info_text += "\n🔊 <b>Pistes audio</b>:\n"
                    for i, track in enumerate(media_info.audio_tracks, 1):
                        lang_name = LANGUAGE_NAMES.get(track.language, track.language or "Inconnu")
                        codec_name = str(track.codec).split('.')[-1] if track.codec else "Inconnu"
                        info_text += (
                            f"  {i}. {lang_name} | "
                            f"Codec: {codec_name} | "
                            f"Canaux: {track.channels or 2} | "
                            f"{'🔹 Par défaut' if track.is_default else ''}\n"
                        )
                
                if hasattr(media_info, 'subtitle_tracks') and media_info.subtitle_tracks:
                    info_text += "\n📝 <b>Sous-titres</b>:\n"
                    for i, sub in enumerate(media_info.subtitle_tracks, 1):
                        lang_name = LANGUAGE_NAMES.get(sub.language, sub.language or "Inconnu")
                        info_text += f"  {i}. {lang_name} | Format: {sub.codec or 'Inconnu'}\n"
                
               
                
                await status_msg.edit(
                    text=info_text,
                    disable_web_page_preview=True
                )
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur d'analyse: {str(e)}")
            finally:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    os.rmdir(user_dir)
                except:
                    pass
                    
        except Exception as e:
            await callback_query.answer(f"Erreur: {str(e)}", show_alert=True)
    
    elif data == "convert_audio":
        try:
            await callback_query.answer("⏳ Conversion audio en préparation...")

            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return

            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)

            try:
                status_msg = await msg.edit("⏳ Téléchargement en cours...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement en cours...")

            try:
                file_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/original.mp4",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            try:
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)

                media_info = await videoclient.get_media_info(file_path)

                if not media_info.audio_tracks:
                    await status_msg.edit("❌ Aucune piste audio trouvée")
                    return

                # Dictionnaire langues
                LANGUAGE_NAMES = {
                    'jpn': "Japonais", 'eng': "Anglais", 'fre': "Français",
                    'spa': "Espagnol", 'ger': "Allemand", 'ita': "Italien"
                }

                # Demander format
                await status_msg.edit(
                    "🛠 <b>Choisissez le format de conversion :</b>\n\n"
                    "Options disponibles : MP3, AAC, OGG, WAV\n\n"
                    "Répondez avec le nom du format souhaité :"
                )

                try:
                    format_response = await client.listen(
                        filters.text & filters.user(user.id),
                        timeout=60
                    )
                    format_choice = format_response.text.strip().lower()
                    if format_choice not in ["mp3", "aac", "ogg", "wav"]:
                        await status_msg.edit("❌ Format invalide. Veuillez choisir entre MP3, AAC, OGG ou WAV")
                        return
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé - opération annulée")
                    return
                await format_response.delete()
                # Traiter chaque piste audio
                for track in media_info.audio_tracks:
                    lang_name = LANGUAGE_NAMES.get(track.language, track.language or "Inconnu")
                    track_name = f"Piste {track.index} ({lang_name})"

                    await status_msg.edit(f"⚙️ Conversion de {track_name} en {format_choice.upper()}...")

                    audio_path = await videoclient.convert_audio(
                        input_path=file_path,
                        output_name=f"piste_{track.index}_{format_choice}",
                        codec=AudioCodec[format_choice.upper()],
                        bitrate=192,
                    )

                    if audio_path:
                        caption = (
                            f"🎧 {track_name}\n"
                            f"├ Format: {format_choice.upper()}\n"
                            f"├ Canaux: {track.channels or 2}\n"
                            f"└ Qualité: 192 kbps"
                        )

                        await client.send_audio(
                            chat_id=user.id,
                            audio=audio_path,
                            caption=caption,
                            title=f"{track_name} ({format_choice.upper()})",
                            performer=f"By @{me.first_name}",
                            progress=progress_for_pyrogram,
                            progress_args=(f"Envoi {track_name}...", status_msg, time.time())
                        )

                        try:
                            os.remove(audio_path)
                        except:
                            pass

                await status_msg.edit("✅ Conversion terminée avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()

            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")

        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur nettoyage: {str(e)}")
    
    elif data == "video_trim":
        try:
            await callback_query.answer("⏳ Découpage vidéo en préparation...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement en cours...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement en cours...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                if original_filename:
                    filename_without_ext = os.path.splitext(original_filename)[0]
                    download_filename = f"{user_dir}/{filename_without_ext}_original{os.path.splitext(original_filename)[1] or '.mp4'}"
                else:
                    download_filename = f"{user_dir}/original.mp4"
                
                file_path = await msg.reply_to_message.download(
                    file_name=download_filename,
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            try:
                videoclient = deps.videoclient
                original_media_info = await videoclient.get_media_info(file_path)
                original_duration = int(original_media_info.duration) if original_media_info and hasattr(original_media_info, 'duration') else 0
            except Exception as e:
                print(f"⚠️ Erreur lecture infos média originales: {str(e)}")
                original_duration = 0

            trim_instructions = (
                "✂️ <b>Format attendu</b> : <code>HH:MM:SS-HH:MM:SS</code>\n"
                f"Durée totale: {seconds_to_timestamp(original_duration)}\n\n"
                "Exemple :\n"
                "<code>00:01:30-00:02:45</code> pour une séquence\n\n"
                "Envoyez maintenant le temps de découpage :"
            )
            
            await status_msg.edit(trim_instructions)
            
            try:
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=120
                )
                
                if "-" not in response.text:
                    await status_msg.edit("❌ Format incorrect. Utilisez HH:MM:SS-HH:MM:SS")
                    return
                
                start_time_str, end_time_str = response.text.strip().split("-")
                
                def validate_time(time_str):
                    parts = time_str.split(":")
                    if len(parts) == 3:  # HH:MM:SS
                        return True
                    elif len(parts) == 2:  # MM:SS
                        return True
                    return False
                    
                if not validate_time(start_time_str) or not validate_time(end_time_str):
                    await status_msg.edit("❌ Format de temps invalide")
                    return
                    
                start_time = convert_to_seconds(start_time_str)
                end_time = convert_to_seconds(end_time_str)
                
                await response.delete()
                
                if start_time >= end_time:
                    await status_msg.edit("❌ Le temps de fin doit être après le temps de début")
                    return
                    
                if original_duration > 0 and end_time > original_duration:
                    await status_msg.edit(f"❌ La fin ({end_time_str}) dépasse la durée totale ({seconds_to_timestamp(original_duration)})")
                    return
                    
                await status_msg.edit(f"✂️ Découpage de {start_time_str} à {end_time_str}...")
                
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.trim_video(
                    input_path=file_path,
                    output_name="trimmed",
                    start_time=start_time,
                    end_time=end_time
                )
                
                if not result or not os.path.exists(result):
                    await status_msg.edit("❌ Échec du découpage vidéo")
                    return
                    
                try:
                    result_media_info = await videoclient.get_media_info(result)
                    width = result_media_info.width if result_media_info and hasattr(result_media_info, 'width') else 320
                    height = result_media_info.height if result_media_info and hasattr(result_media_info, 'height') else None
                    duration = int(result_media_info.duration) if result_media_info and hasattr(result_media_info, 'duration') else (end_time - start_time)
                except Exception as e:
                    print(f"⚠️ Erreur lecture infos média résultat: {str(e)}")
                    width = 320
                    height = None
                    duration = end_time - start_time 
                
                try:
                    await client.send_video(
                        chat_id=user.id,
                        video=result,
                        width=width,
                        height=height,
                        duration=duration,
                        caption=f"✂️ Vidéo découpée: {start_time_str} à {end_time_str}",
                        progress=progress_for_pyrogram,
                        progress_args=("Envoi...", status_msg, time.time())
                    )
                    await asyncio.sleep(1)
                except Exception as send_error:
                    await status_msg.edit(f"❌ Erreur d'envoi: {str(send_error)}")
                    await client.send_message(
                        chat_id=user.id,
                        text=f"❌ Impossible d'envoyer la vidéo: {str(send_error)}"
                    )
                finally:
                    try:
                        os.remove(result)
                    except Exception as clean_error:
                        print(f"Erreur suppression fichier: {str(clean_error)}")
                
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("❌ Temps écoulé (120s)")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
                await client.send_message(
                    chat_id=user.id,
                    text=f"❌ Échec du découpage: {str(e)}"
                )
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur nettoyage: {str(e)}")
    
    
    elif data == "video_merge":
        try:
            await callback_query.answer("⏳ Fusion vidéo en préparation...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Répondez à une vidéo pour commencer", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la première vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la première vidéo...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                if original_filename:
                    filename_without_ext = os.path.splitext(original_filename)[0]
                    first_video_path = f"{user_dir}/{filename_without_ext}_0{os.path.splitext(original_filename)[1] or '.mp4'}"
                else:
                    first_video_path = f"{user_dir}/video_0.mp4"
                
                first_video_path = await msg.reply_to_message.download(
                    file_name=first_video_path,
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement vidéo 1...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            users_operations[user.id] = {
                'dir': user_dir,
                'video_paths': [first_video_path],
                'status_msg': status_msg,
                'original_filenames': [original_filename] if original_filename else []
            }
            
            await status_msg.edit(
                "📹 <b>Fusion vidéo</b>\n\n"
                f"1. {original_filename or os.path.basename(first_video_path)} (vidéo de départ)\n\n"
                "Envoyez maintenant les autres vidéos à fusionner (une par message)\n\n"
                "Tapez /done quand vous avez terminé\n"
                "Tapez /cancel pour annuler"
            )
            
            while True:
                try:
                    response = await client.listen(
                        filters=(filters.video | filters.document | filters.text) & filters.user(user.id),
                        timeout=120
                    )
                    
                    if response.text:
                        if "/done" in response.text:
                            if len(users_operations[user.id]['video_paths']) < 2:
                                await status_msg.edit("❌ Vous devez ajouter au moins une vidéo à fusionner")
                                continue
                            break
                        elif "/cancel" in response.text:
                            await status_msg.edit("❌ Fusion annulée")
                            return
                        continue
                    
                    try:
                        video_num = len(users_operations[user.id]['video_paths'])
                        original_filename = None
                        if response.document:
                            original_filename = response.document.file_name
                        elif response.video:
                            original_filename = response.video.file_name
                        
                        if original_filename:
                            filename_without_ext = os.path.splitext(original_filename)[0]
                            new_video_path = f"{user_dir}/{filename_without_ext}_{video_num}{os.path.splitext(original_filename)[1] or '.mp4'}"
                        else:
                            new_video_path = f"{user_dir}/video_{video_num}.mp4"
                        
                        new_video_path = await response.download(
                            file_name=new_video_path,
                            progress=progress_for_pyrogram,
                            progress_args=(f"Téléchargement vidéo {video_num+1}...", status_msg, time.time())
                        )
                        users_operations[user.id]['video_paths'].append(new_video_path)
                        if original_filename:
                            users_operations[user.id]['original_filenames'].append(original_filename)
                        
                        await response.delete()
                        
                        video_list = "\n".join(
                            f"{i+1}. {users_operations[user.id]['original_filenames'][i] if i < len(users_operations[user.id]['original_filenames']) else os.path.basename(p)}"
                            for i, p in enumerate(users_operations[user.id]['video_paths'])
                        )
                        await status_msg.edit(
                            f"📹 <b>Vidéos à fusionner ({len(users_operations[user.id]['video_paths'])})</b>\n\n"
                            f"{video_list}\n\n"
                            "Envoyez d'autres vidéos ou tapez /done pour continuer\n"
                            "Tapez /cancel pour annuler"
                        )
                        
                    except Exception as e:
                        await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                        continue
                        
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé - opération annulée")
                    return
            await response.delete()

            await status_msg.edit(
                    "🛠 <b>Choisissez l'extension de sortie :</b>\n\n"
                    "Options disponibles : `MP4` `MKV` `AVI` \n\n"
                    "Envoyer `!annuler` pour annuler\n\n"
                    "Répondez avec le nom du format souhaité :"
                )
            try:
                format_response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=60
                )
                
                if format_response.text == "!annuler":
                    await status_msg.edit("❌ Fusion annulée")
                    return
                    
                output_format = MediaType(format_response.text.lower())
                
                await format_response.delete()
                
                await status_msg.edit(
                    "⏳ <b>Durée de transition entre les vidéos (en secondes) :</b>\n\n"
                    "Entrez un nombre entre 0 et 5 (0 pour pas de transition) :"
                )
                
                transition_response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=60
                )
                
                try:
                    transition_duration = float(transition_response.text.strip())
                    if transition_duration < 0 or transition_duration > 5:
                        raise ValueError
                except:
                    await status_msg.edit("❌ Durée invalide. Utilisez un nombre entre 0 et 5")
                    return
                await transition_response.delete()
                
                await status_msg.edit("⚙️ Fusion des vidéos en cours...")
                
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.concat_video(
                    input_paths=users_operations[user.id]['video_paths'],
                    output_name="merged",
                    output_format=output_format,
                    transition_duration=transition_duration
                )
                
                if not result or not os.path.exists(result):
                    await status_msg.edit("❌ Échec de la fusion des vidéos")
                    return
                    
                try:
                    result_media_info = await videoclient.get_media_info(result)
                    width = result_media_info.width if result_media_info and hasattr(result_media_info, 'width') else 1280
                    height = result_media_info.height if result_media_info and hasattr(result_media_info, 'height') else 720
                    duration = int(result_media_info.duration) if result_media_info and hasattr(result_media_info, 'duration') else 0
                except Exception as e:
                    print(f"⚠️ Erreur lecture infos média résultat: {str(e)}")
                    width = 1280
                    height = 720
                    duration = 0
                
                try:
                    await client.send_video(
                        chat_id=user.id,
                        video=result,
                        width=width,
                        height=height,
                        duration=duration,
                        caption=f"📼 Vidéo fusionnée ({len(users_operations[user.id]['video_paths'])} clips)",
                        progress=progress_for_pyrogram,
                        progress_args=("Envoi...", status_msg, time.time())
                    )
                    await asyncio.sleep(1)
                except Exception as send_error:
                    await status_msg.edit(f"❌ Erreur d'envoi: {str(send_error)}")
                    await client.send_message(
                        chat_id=user.id,
                        text=f"❌ Impossible d'envoyer la vidéo: {str(send_error)}"
                    )
                finally:
                    try:
                        os.remove(result)
                    except Exception as clean_error:
                        print(f"Erreur suppression fichier: {str(clean_error)}")
                
                await status_msg.edit("✅ Fusion terminée avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
                await client.send_message(
                    chat_id=user.id,
                    text=f"❌ Échec de la fusion: {str(e)}"
                )
        finally:
            if user.id in users_operations:
                try:
                    for path in users_operations[user.id]['video_paths']:
                        try:
                            os.remove(path)
                        except:
                            pass
                    if os.path.exists(user_dir):
                        for root, _, files in os.walk(user_dir):
                            for file in files:
                                try:
                                    os.remove(os.path.join(root, file))
                                except:
                                    pass
                        os.rmdir(user_dir)
                except Exception as e:
                    print(f"Erreur nettoyage: {str(e)}")
                finally:
                    del users_operations[user.id]

    elif data == "video_split":
        def validate_time(time_str):
            parts = time_str.split(":")
            if len(parts) == 3:  # HH:MM:SS
                return all(p.isdigit() for p in parts)
            elif len(parts) == 2:  # MM:SS
                return all(p.isdigit() for p in parts)
            return False

        def convert_to_seconds(time_str):
            parts = list(map(int, time_str.split(":")))
            if len(parts) == 3:  # HH:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:  # MM:SS
                return parts[0] * 60 + parts[1]
            return 0

        def seconds_to_timestamp(seconds):
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        try:
            await callback_query.answer("⏳ Découpage vidéo en préparation...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement en cours...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement en cours...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                download_filename = f"{user_dir}/{original_filename or 'original.mp4'}"
                file_path = await msg.reply_to_message.download(
                    file_name=download_filename,
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            try:
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(file_path)
                total_duration = int(media_info.duration) if media_info else 0
            except Exception as e:
                print(f"⚠️ Erreur lecture durée: {str(e)}")
                total_duration = 0

            cut_instructions = (
                "✂️ <b>Format attendu</b> : <code>HH:MM:SS-HH:MM:SS</code>\n"
                f"Durée totale: {seconds_to_timestamp(total_duration)}\n\n"
                "Exemple :\n"
                "<code>00:01:30-00:02:45</code> pour un segment\n\n"
                "Envoyez les plages séparées par des virgules :"
            )
            
            await status_msg.edit(cut_instructions)
            
            try:
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=120
                )
                
                ranges = []
                for range_str in response.text.strip().split(","):
                    if "-" not in range_str:
                        await status_msg.edit("❌ Format invalide. Utilisez HH:MM:SS-HH:MM:SS")
                        return
                    
                    start_str, end_str = range_str.strip().split("-")
                    
                    if not all(validate_time(t) for t in [start_str, end_str]):
                        await status_msg.edit("❌ Format de temps invalide")
                        return
                    
                    start = convert_to_seconds(start_str)
                    end = convert_to_seconds(end_str)
                    
                    if start >= end:
                        await status_msg.edit("❌ Le temps de fin doit être après le début")
                        return
                    
                    if total_duration > 0 and end > total_duration:
                        await status_msg.edit(f"❌ La fin dépasse la durée totale ({seconds_to_timestamp(total_duration)})")
                        return
                    
                    ranges.append((start, end))
                
                await response.delete()
                
                await status_msg.edit(f"✂️ Découpage de {len(ranges)} segment(s)...")
                results = await videoclient.split_video(
                    input_path=file_path,
                    output_name="segment",
                    cut_ranges=ranges
                )
                
                if not results:
                    await status_msg.edit("❌ Échec du découpage")
                    return
                
                for i, segment_path in enumerate(results):
                    if os.path.exists(segment_path):
                        try:
                            seg_info = await videoclient.get_media_info(segment_path)
                            width = seg_info.width if seg_info else 1280
                            height = seg_info.height if seg_info else 720
                            duration = int(seg_info.duration) if seg_info else (ranges[i][1] - ranges[i][0])
                            
                            await client.send_video(
                                chat_id=user.id,
                                video=segment_path,
                                width=width,
                                height=height,
                                duration=duration,
                                caption=f"✂️ Segment {i+1}: {seconds_to_timestamp(ranges[i][0])}-{seconds_to_timestamp(ranges[i][1])}",
                                progress=progress_for_pyrogram,
                                progress_args=(f"Envoi segment {i+1}...", status_msg, time.time())
                            )
                            await asyncio.sleep(1)
                        except Exception as e:
                            await status_msg.edit(f"❌ Erreur envoi segment {i+1}: {str(e)}")
                        finally:
                            try:
                                os.remove(segment_path)
                            except:
                                pass
                
                await status_msg.edit("✅ Découpage terminé!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
                
        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur nettoyage: {str(e)}")
    
    elif data == "generate_thumbnail":
        try:
            await callback_query.answer("⏳ Préparation de la miniature...")
            
            # Vérification du fichier source
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            # Création du dossier utilisateur
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            # Téléchargement du fichier
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")
            
            try:
                file_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/source_video.mp4",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            # Demande des paramètres de la miniature
            thumbnail_instructions = (
                "🖼 <b>Paramètres de la miniature</b>\n\n"
                "1. <b>Position temporelle</b> (format HH:MM:SS)\n"
                "Exemple: <code>00:01:30</code> pour 1 minute 30 secondes\n\n"
                "2. <b>Largeur</b> (en pixels, entre 100 et 1280)\n\n"
                "Répondez avec les valeurs séparées par un espace, exemple:\n"
                "<code>00:01:30 640</code>"
            )
            
            await status_msg.edit(thumbnail_instructions)
            
            try:
                # Attente de la réponse utilisateur
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=120
                )
                
                # Traitement de la réponse
                parts = response.text.strip().split()
                if len(parts) == 1:
                    time_offset = parts[0]
                    width = 320  # Valeur par défaut
                elif len(parts) == 2:
                    time_offset, width = parts
                    try:
                        width = int(width)
                        if not 100 <= width <= 1280:
                            raise ValueError
                    except ValueError:
                        await status_msg.edit("❌ Largeur invalide (doit être entre 100 et 1280)")
                        return
                else:
                    await status_msg.edit("❌ Format incorrect. Utilisez: HH:MM:SS [largeur]")
                    return
                
                # Validation du format temporel
                def validate_time(time_str):
                    parts = time_str.split(":")
                    if len(parts) == 3:  # HH:MM:SS
                        return True
                    elif len(parts) == 2:  # MM:SS
                        return True
                    return False
                    
                if not validate_time(time_offset):
                    await status_msg.edit("❌ Format de temps invalide. Utilisez HH:MM:SS")
                    return
                
                await response.delete()
                
                # Génération de la miniature
                await status_msg.edit(f"⚙️ Génération de la miniature à {time_offset}...")
                
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.generate_thumbnail(
                    input_path=file_path,
                    output_name="thumbnail",
                    time_offset=time_offset,
                    width=width
                )
                
                if not result:
                    await status_msg.edit("❌ Échec de la génération de la miniature")
                    return
                    
                # Envoi du résultat
                await client.send_photo(
                    chat_id=user.id,
                    photo=result,
                    caption=(
                        f"🖼 Miniature générée\n"
                        f"⏱ Position: {time_offset}\n"
                        f"📏 Dimensions: {width}x{'auto'}"
                    ),
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                
                await status_msg.edit("✅ Miniature générée avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            # Nettoyage complet
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        try:
                            os.remove(os.path.join(root, file))
                        except:
                            pass
                os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur lors du nettoyage: {str(e)}")
    
    elif data == "merge_video_audio":
        try:
            await callback_query.answer("⏳ Fusion vidéo/audio en préparation...")

            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Répondez à une vidéo", show_alert=True)
                return

            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)

            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")

            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name

                video_filename = f"{user_dir}/{original_filename or 'video_source.mp4'}"
                video_path = await msg.reply_to_message.download(
                    file_name=video_filename,
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement vidéo...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement vidéo: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            await status_msg.edit(
                "🎵 <b>Maintenant envoyez le fichier audio</b>\n\n"
                "Format supporté: MP3, AAC, WAV\n\n"
                "Tapez /cancel pour annuler"
            )

            try:
                audio_response = await client.listen(
                    filters=(filters.audio | filters.document | filters.text) & filters.user(user.id),
                    timeout=120
                )

                if audio_response.text and "/cancel" in audio_response.text:
                    await status_msg.edit("❌ Fusion annulée")
                    return

                await status_msg.edit("⏳ Téléchargement de l'audio...")

                audio_original_name = None
                if audio_response.document:
                    audio_original_name = audio_response.document.file_name
                elif audio_response.audio:
                    audio_original_name = audio_response.audio.file_name

                audio_filename = f"{user_dir}/{audio_original_name or 'audio_source.mp3'}"
                audio_path = await audio_response.download(
                    file_name=audio_filename,
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement audio...", status_msg, time.time())
                )

                await audio_response.delete()

                await status_msg.edit("⚙️ Fusion vidéo/audio en cours...")

                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)

                result = await videoclient.merge_video_audio(
                    video_path=video_path,
                    audio_path=audio_path,
                    output_name="merged"
                )

                if not result or not os.path.exists(result):
                    await status_msg.edit("❌ Échec de la fusion")
                    return

                # Obtenir les infos de la vidéo fusionnée
                try:
                    media_info = await videoclient.get_media_info(result)
                    width = media_info.width if media_info else 1280
                    height = media_info.height if media_info else 720
                    duration = int(media_info.duration) if media_info else 0
                except Exception as e:
                    print(f"⚠️ Erreur lecture info fusionnée: {str(e)}")
                    width, height, duration = 1280, 720, 0

                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    width=width,
                    height=height,
                    duration=duration,
                    caption="🎬 Vidéo avec nouvel audio",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )

                await status_msg.edit("✅ Fusion terminée avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()

            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                for file in [video_path, audio_path, result]:
                    try:
                        if file and os.path.exists(file):
                            os.remove(file)
                    except:
                        pass
                if os.path.exists(user_dir):
                    for root, _, files in os.walk(user_dir):
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except:
                                pass
                    os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur nettoyage: {str(e)}")
    
    elif data == "remove_audio":
        try:
            await callback_query.answer("⏳ Suppression de l'audio en cours...")

            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return

            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)

            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")

            try:
                file_name = msg.reply_to_message.file_name or "original.mp4"
                input_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/{file_name}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                shutil.rmtree(user_dir, ignore_errors=True)
                return

            await status_msg.edit(
                "🔇 <b>Supprimer l'audio de cette vidéo?</b>\n\n"
                f"Fichier: <code>{os.path.basename(input_path)}</code>\n\n"
                "Tapez /cancel pour annuler, /done pour confirmer"
            )

            try:
                response = await client.listen(filters.text & filters.user(user.id), timeout=60)

                if response.text.strip().lower() == "/cancel":
                    await status_msg.edit("❌ Opération annulée")
                    return
                elif response.text.strip().lower() != "/done":
                    await status_msg.edit("❌ Réponse invalide. Tapez /done ou /cancel.")
                    return

            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
                return

            await response.delete()

            await status_msg.edit("⚙️ Suppression de l'audio...")

            videoclient = deps.videoclient
            videoclient.output_path = Path(user_dir)

            result = await videoclient.remove_audio(
                input_path=input_path,
                output_name="no_audio"
            )

            if not result:
                await status_msg.edit("❌ Échec de la suppression de l'audio")
                return

            info = await videoclient.get_media_info(result)

            await client.send_document(
                chat_id=user.id,
                document=result,
                caption=f"🎬 Vidéo sans audio\n\n📄 <code>{os.path.basename(result)}</code>\n\n{info}",
                force_document=True,
                progress=progress_for_pyrogram,
                progress_args=("Envoi...", status_msg, time.time())
            )

            await status_msg.edit("✅ Audio supprimé avec succès!")
            await asyncio.sleep(2)
            await status_msg.delete()

        except Exception as e:
            await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                shutil.rmtree(user_dir, ignore_errors=True)
            except Exception as e:
                print(f"Erreur de nettoyage: {str(e)}")

    
    elif data == "subtitle_extract":
        try:
            await callback_query.answer("⏳ Extraction des sous-titres...")
            
            # Vérification du fichier source
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            # Création du dossier temporaire
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            # Téléchargement du fichier
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")
            
            try:
                input_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/original.mp4",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            # Demande de confirmation
            await status_msg.edit(
                "📝 <b>Extraire les sous-titres de cette vidéo?</b>\n\n"
                f"Fichier: {os.path.basename(input_path)}\n\n"
                "Tapez /confirm pour continuer ou /cancel pour annuler"
            )
            
            try:
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=60
                )
                
                if response.text.strip().lower() == "/cancel":
                    await status_msg.edit("❌ Opération annulée")
                    return
                elif response.text.strip().lower() != "/confirm":
                    await status_msg.edit("❌ Commande invalide. Opération annulée")
                    return
                    
                await response.delete()
                
                # Extraction des sous-titres
                await status_msg.edit("⚙️ Extraction des sous-titres...")
                
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                subtitle_files = await videoclient.extract_subtitles(
                    input_path=input_path,
                    output_dir=user_dir,
                )
                
                if not subtitle_files or not isinstance(subtitle_files, list):
                    await status_msg.edit("❌ Aucun sous-titre trouvé ou erreur d'extraction")
                    return
                    
                for sub_file in subtitle_files:
                    if os.path.exists(sub_file):
                        await client.send_document(
                            chat_id=user.id,
                            document=sub_file,
                            caption=f"📝 Sous-titre extrait: {os.path.basename(sub_file)}",
                            force_document=True,
                            progress=progress_for_pyrogram,
                            progress_args=("Envoi...", status_msg, time.time())
                        )
                        os.remove(sub_file)  
                        await asyncio.sleep(1)
                await status_msg.edit("✅ Extraction terminée avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            # Nettoyage complet
            try:
                if 'input_path' in locals() and os.path.exists(input_path):
                    os.remove(input_path)
                if 'user_dir' in locals() and os.path.exists(user_dir):
                    for root, _, files in os.walk(user_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                            except:
                                pass
                    os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur lors du nettoyage: {str(e)}")
                
    elif data == "subtitle_add":
        try:
            await callback_query.answer("⏳ Ajout de sous-titres en cours...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                video_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/{original_filename or 'original.mp4'}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement vidéo...", status_msg, time.time())
                )
                
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(video_path)
                width = media_info.width if media_info else 1280
                height = media_info.height if media_info else 720
                duration = int(media_info.duration) if media_info else 0
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement vidéo: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            await status_msg.edit(
                "📜 <b>Envoyez maintenant le fichier de sous-titres</b>\n\n"
                f"📹 Vidéo: {original_filename or 'video'}\n"
                f"📏 Résolution: {width}x{height}\n"
                f"⏱ Durée: {duration // 60}:{duration % 60:02d}\n\n"
                "Formats supportés: .srt, .vtt, .ass\n\n"
                "Tapez /cancel pour annuler"
            )
            
            try:
                subtitle_response = await client.listen(
                    filters=(filters.document | filters.text) & filters.user(user.id),
                    timeout=120
                )
                
                if subtitle_response.text and "/cancel" in subtitle_response.text.lower():
                    await status_msg.edit("❌ Opération annulée")
                    return
                    
                await status_msg.edit("⏳ Téléchargement des sous-titres...")
                subtitle_path = await subtitle_response.download(
                    file_name=f"{user_dir}/subtitles.{subtitle_response.document.file_name.split('.')[-1]}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement sous-titres...", status_msg, time.time())
                )
                
                await status_msg.edit("⚙️ Ajout des sous-titres...")
                videoclient.output_path = Path(user_dir)
                
                temp_video = await videoclient.remove_subtitles(
                    input_path=video_path,
                    output_name="no_subtitles"
                )
                if not temp_video:
                    await status_msg.edit("❌ Échec du nettoyage des sous-titres existants")
                    return
                await subtitle_response.delete()
                
                result = await videoclient.add_subtitle(
                    input_path=temp_video,
                    sbt_file=subtitle_path,
                    language="french",
                    output_name="final_output",
                    is_forced=False,
                )
                
                if not result:
                    await status_msg.edit("❌ Échec de l'ajout des sous-titres")
                    return
                    
                result_info = await videoclient.get_media_info(result)
                result_width = result_info.width if result_info else width
                result_height = result_info.height if result_info else height
                result_duration = int(result_info.duration) if result_info else duration
                
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    width=result_width,
                    height=result_height,
                    duration=result_duration,
                    caption="🎬 Vidéo avec sous-titres ajoutés",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                
                await status_msg.edit("✅ Sous-titres ajoutés avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                for file in [locals().get("video_path"), locals().get("subtitle_path"), locals().get("temp_video"), locals().get("result")]:
                    if file and os.path.exists(file):
                        try:
                            os.remove(file)
                        except Exception as e:
                            print(f"Erreur suppression fichier {file}: {e}")
                
                if os.path.exists(user_dir):
                    for root, _, files in os.walk(user_dir):
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except Exception as e:
                                print(f"Erreur suppression dans {root}: {e}")
                    try:
                        os.rmdir(user_dir)
                    except Exception as e:
                        print(f"Erreur suppression dossier {user_dir}: {e}")
            except Exception as e:
                print(f"Erreur lors du nettoyage général: {str(e)}")
                
    elif data == "force_subtitle":
        try:
            await callback_query.answer("⏳ Ajout de sous-titres forcés en cours...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                video_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/{original_filename or 'original.mp4'}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement vidéo...", status_msg, time.time())
                )
                
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(video_path)
                width = media_info.width if media_info else 1280
                height = media_info.height if media_info else 720
                duration = int(media_info.duration) if media_info else 0
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement vidéo: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            await status_msg.edit(
                "📜 <b>Envoyez maintenant le fichier de sous-titres FORCÉS</b>\n\n"
                f"📹 Vidéo: {original_filename or 'video'}\n"
                f"📏 Résolution: {width}x{height}\n"
                f"⏱ Durée: {duration // 60}:{duration % 60:02d}\n\n"
                "Formats supportés: .srt, .vtt, .ass\n\n"
                "Les sous-titres seront marqués comme forcés (toujours affichés)\n\n"
                "Tapez /cancel pour annuler"
            )
            
            try:
                subtitle_response = await client.listen(
                    filters=(filters.document | filters.text) & filters.user(user.id),
                    timeout=120
                )
                
                if subtitle_response.text and "/cancel" in subtitle_response.text.lower():
                    await status_msg.edit("❌ Opération annulée")
                    return
                    
                await status_msg.edit("⏳ Téléchargement des sous-titres...")
                subtitle_ext = subtitle_response.document.file_name.split('.')[-1]
                subtitle_path = await subtitle_response.download(
                    file_name=f"{user_dir}/subtitles_forced.{subtitle_ext}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement sous-titres...", status_msg, time.time())
                )
                
                await status_msg.edit("⚙️ Ajout des sous-titres forcés...")
                videoclient.output_path = Path(user_dir)
                
                temp_video = await videoclient.remove_subtitles(
                    input_path=video_path,
                    output_name="no_subtitles"
                )
                if not temp_video:
                    await status_msg.edit("❌ Échec du nettoyage des sous-titres existants")
                    return
                await subtitle_response.delete()
                
                result = await videoclient.add_subtitle(
                    input_path=temp_video,
                    sbt_file=subtitle_path,
                    language="french",
                    output_name="forced_subtitles_output",
                    is_forced=True,
                )
                
                if not result:
                    await status_msg.edit("❌ Échec de l'ajout des sous-titres forcés")
                    return
                    
                result_info = await videoclient.get_media_info(result)
                result_width = result_info.width if result_info else width
                result_height = result_info.height if result_info else height
                result_duration = int(result_info.duration) if result_info else duration
                
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    width=result_width,
                    height=result_height,
                    duration=result_duration,
                    caption="🎬 Vidéo avec sous-titres forcés ajoutés",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                
                await status_msg.edit("✅ Sous-titres forcés ajoutés avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                for file in [locals().get("video_path"), 
                           locals().get("subtitle_path"), 
                           locals().get("temp_video"), 
                           locals().get("result")]:
                    if file and os.path.exists(file):
                        try:
                            os.remove(file)
                        except Exception as e:
                            print(f"Erreur suppression fichier {file}: {e}")
                
                if os.path.exists(user_dir):
                    for root, _, files in os.walk(user_dir):
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except Exception as e:
                                print(f"Erreur suppression dans {root}: {e}")
                    try:
                        os.rmdir(user_dir)
                    except Exception as e:
                        print(f"Erreur suppression dossier {user_dir}: {e}")
            except Exception as e:
                print(f"Erreur lors du nettoyage général: {str(e)}")

    elif data == "remove_subtitles":
        try:
            await callback_query.answer("⏳ Suppression des sous-titres en cours...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement du fichier vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement du fichier vidéo...")
            
            try:
                original_filename = None
                if msg.reply_to_message.document:
                    original_filename = msg.reply_to_message.document.file_name
                elif msg.reply_to_message.video:
                    original_filename = msg.reply_to_message.video.file_name
                
                input_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/{original_filename or 'original.mp4'}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
                
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(input_path)
                width = media_info.width if media_info else 1280
                height = media_info.height if media_info else 720
                duration = int(media_info.duration) if media_info else 0
                has_subtitles = media_info.has_subtitles if media_info else False
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return
            
            await status_msg.edit(
                "❌ <b>Supprimer les sous-titres de cette vidéo?</b>\n\n"
                f"📹 Fichier: {original_filename or 'video'}\n"
                f"📏 Résolution: {width}x{height}\n"
                f"⏱ Durée: {duration // 60}:{duration % 60:02d}\n"
                f"🔤 Sous-titres détectés: {'Oui' if has_subtitles else 'Non'}\n\n"
                "Tapez /confirm pour continuer ou /cancel pour annuler"
            )
            
            try:
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=60
                )
                
                if response.text.strip().lower() == "/cancel":
                    await status_msg.edit("❌ Opération annulée")
                    return
                elif response.text.strip().lower() != "/confirm":
                    await status_msg.edit("❌ Commande invalide. Opération annulée")
                    return
                    
                await response.delete()
                
                # Traitement de la vidéo
                await status_msg.edit("⚙️ Suppression des sous-titres...")
                
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.remove_subtitles(
                    input_path=input_path,
                    output_name="no_subtitles"
                )
                
                if not result:
                    await status_msg.edit("❌ Échec de la suppression des sous-titres")
                    return
                
                result_info = await videoclient.get_media_info(result)
                result_width = result_info.width if result_info else width
                result_height = result_info.height if result_info else height
                result_duration = int(result_info.duration) if result_info else duration
                    
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    width=result_width,
                    height=result_height,
                    duration=result_duration,
                    caption="🎬 Vidéo sans sous-titres",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                
                await status_msg.edit("✅ Sous-titres supprimés avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                for file in [locals().get("input_path"), locals().get("result")]:
                    if file and os.path.exists(file):
                        try:
                            os.remove(file)
                        except Exception as e:
                            print(f"Erreur suppression fichier {file}: {e}")
                
                if os.path.exists(user_dir):
                    for root, _, files in os.walk(user_dir):
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except Exception as e:
                                print(f"Erreur suppression dans {root}: {e}")
                    try:
                        os.rmdir(user_dir)
                    except Exception as e:
                        print(f"Erreur suppression dossier {user_dir}: {e}")
            except Exception as e:
                print(f"Erreur de nettoyage: {str(e)}")
    
    elif data in ["choose_subtitle", "choose_subtitle_burn"]:
        status_msg = None
        try:
            await callback_query.answer("⏳ Traitement des sous-titres en cours...")

            if not msg.reply_to_message:
                await callback_query.answer("❌ Aucun message auquel répondre", show_alert=True)
                return

            reply_msg = msg.reply_to_message
            if not (reply_msg.video or (reply_msg.document and reply_msg.document.mime_type.startswith('video/'))):
                await callback_query.answer("❌ Aucun fichier vidéo valide trouvé", show_alert=True)
                return

            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)

            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")

            try:
                if reply_msg.video:
                    original_filename = reply_msg.video.file_name or "video.mp4"
                else:
                    original_filename = reply_msg.document.file_name or "video.mp4"

                input_path = await reply_msg.download(
                    file_name=f"{user_dir}/{original_filename}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )

                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(input_path)

                if not media_info:
                    await status_msg.edit("❌ Impossible d'analyser le fichier vidéo")
                    return

                duration = int(media_info.duration) if media_info.duration else 0
                width = media_info.width if media_info.width else 1280
                height = media_info.height if media_info.height else 720

            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                shutil.rmtree(user_dir, ignore_errors=True)
                return

            if not media_info.subtitle_tracks:
                await status_msg.edit("❌ Aucune piste de sous-titres détectée dans le fichier")
                shutil.rmtree(user_dir, ignore_errors=True)
                return

            subtitle_options = []
            lang_counter = {}

            for index, track in enumerate(media_info.subtitle_tracks):
                lang = track.language.lower() if track.language else "inconnu"
                lang_counter[lang] = lang_counter.get(lang, 0) + 1
                count = lang_counter[lang]
                display_name = f"{lang.capitalize()} ({count})" if count > 1 else lang.capitalize()
                subtitle_options.append({
                    'index': index,
                    'lang_code': lang,
                    'display': display_name
                })

            keyboard = []
            current_row = []
            for i, option in enumerate(subtitle_options):
                current_row.append(KeyboardButton(text=option['display']))
                if (i + 1) % 2 == 0 or i + 1 == len(subtitle_options):
                    keyboard.append(current_row)
                    current_row = []

            keyboard.append([KeyboardButton(text="❌ Annuler")])

            reply_markup = ReplyKeyboardMarkup(
                keyboard=keyboard,
                resize_keyboard=True,
                one_time_keyboard=True
            )

            action = "brûler" if data == "choose_subtitle_burn" else "sélectionner"
            languages_text = "\n".join(f"- {opt['display']}" for opt in subtitle_options)

            await status_msg.edit(
                f"🎬 <b>Choisissez la piste de sous-titres à {action}</b>\n\n"
                f"📹 Fichier: {original_filename}\n"
                f"📏 Résolution: {width}x{height}\n"
                f"⏱ Durée: {duration // 60}:{duration % 60:02d}\n\n"
                f"Pistes disponibles (index FFmpeg):\n{languages_text}",
                reply_markup=reply_markup
            )

            try:
                response = await client.listen(
                    filters=(filters.text & filters.user(user.id)),
                    timeout=120
                )

                if response.text.strip().lower() in ("❌ annuler", "/cancel"):
                    await msg.reply("❌ Opération annulée", reply_markup=ReplyKeyboardRemove())
                    await response.delete()
                    return

                selected_display = response.text.strip()
                selected_option = next((opt for opt in subtitle_options if opt['display'] == selected_display), None)

                if not selected_option:
                    await msg.reply("❌ Sélection invalide", reply_markup=ReplyKeyboardRemove())
                    await response.delete()
                    return

                await response.delete()
                await status_msg.delete()

                selected_lang = selected_option['lang_code']
                track_index = selected_option['index'] + 1

                status_msg = await msg.reply(
                    f"⚙️ {action.capitalize()} la piste {selected_lang.capitalize()} (Index: {track_index})...",
                    reply_markup=ReplyKeyboardRemove()
                )

                output_name = f"output_{selected_lang}_{int(time.time())}"

                if data == "choose_subtitle":
                    result = await videoclient.choose_subtitle(
                        input_path=input_path,
                        output_name=output_name,
                        language=selected_lang,
                        index=track_index,
                        make_default=True,
                    )
                else:
                    result = await videoclient.choose_subtitle_burn(
                        input_path=input_path,
                        output_name=output_name,
                        language=selected_lang,
                        index=track_index,
                    )

                if not result:
                    await status_msg.edit(f"❌ Échec du traitement de la piste {track_index}")
                    return

                result_info = await videoclient.get_media_info(result)
                result_width = result_info.width if result_info else width
                result_height = result_info.height if result_info else height
                result_duration = int(result_info.duration) if result_info and result_info.duration else duration

                caption_action = "brûlés" if data == "choose_subtitle_burn" else "ajoutés"
                caption = f"🎬 Vidéo avec sous-titres {selected_lang.capitalize()} {caption_action} (Piste {track_index})"

                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    width=result_width,
                    height=result_height,
                    duration=result_duration,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                await status_msg.delete()
                await msg.reply(f"✅ Piste {track_index} {action} avec succès!")

            except asyncio.TimeoutError:
                await msg.reply("⌛ Temps écoulé - opération annulée", reply_markup=ReplyKeyboardRemove())
            except Exception as e:
                await msg.reply(f"❌ Erreur: {str(e)}", reply_markup=ReplyKeyboardRemove())

        finally:
            try:
                for file in [locals().get("input_path"), locals().get("result")]:
                    if file and os.path.exists(file):
                        os.remove(file)
                if os.path.exists(user_dir):
                    shutil.rmtree(user_dir, ignore_errors=True)
            except Exception as e:
                print(f"Erreur lors du nettoyage: {str(e)}")

    
    elif data in ["add_chapters", "edit_chapter", "split_chapter", "remove_chapters", "get_chapters", "get_chapter"]:
        # Variables à nettoyer
        input_path = None
        result = None
        chapter_file = None
        response = None
        status_msg = None
        
        try:
            await callback_query.answer("⏳ Traitement des chapitres en cours...")
            
            # Création du dossier temporaire
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            # Vérification du fichier source avec gestion améliorée
            if not msg.reply_to_message or not (msg.reply_to_message.video or 
                                            (msg.reply_to_message.document and 
                                            msg.reply_to_message.document.mime_type.startswith('video/'))):
                try:
                    status_msg = await msg.edit("📤 Veuillez envoyer le fichier vidéo...")
                    file_msg = await client.listen(
                        filters=(filters.document | filters.video) & filters.user(user.id),
                        timeout=60
                    )
                    
                    if not (file_msg.video or (file_msg.document and file_msg.document.mime_type.startswith('video/'))):
                        await status_msg.edit("❌ Format de fichier non supporté")
                        return
                        
                    reply_msg = file_msg
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé - opération annulée")
                    return
            else:
                reply_msg = msg.reply_to_message
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            
            # Téléchargement avec gestion du nom original et métadonnées
            try:
                # Récupération du nom original
                if reply_msg.video:
                    original_filename = reply_msg.video.file_name or "video.mp4"
                    duration = reply_msg.video.duration
                else:
                    original_filename = reply_msg.document.file_name or "video.mp4"
                    duration = 0
                
                input_path = await reply_msg.download(
                    file_name=f"{user_dir}/{original_filename}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
                
                # Analyse des métadonnées
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(input_path)
                width = media_info.width if media_info else 1280
                height = media_info.height if media_info else 720
                duration = int(media_info.duration) if media_info else duration
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    shutil.rmtree(user_dir, ignore_errors=True)
                except:
                    pass
                return

            try:
                if file_msg:
                    await file_msg.delete()
            except:
                pass
            
            # Initialisation du client vidéo
            videoclient.output_path = Path(user_dir)
            
            if data == "get_chapters":
                # Affichage amélioré des chapitres existants
                chapters = await videoclient.get_chapters(input_path)
                if not chapters:
                    await status_msg.edit(
                        f"ℹ️ Aucun chapitre trouvé dans:\n"
                        f"📹 {original_filename}\n"
                        f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}"
                    )
                    return
                    
                chapters_text = "\n".join(
                    f"{i+1}. {chap.get('title', 'Sans titre')} "
                    f"(de {chap['start']} à {chap['end']})"
                    for i, chap in enumerate(chapters)
                )
                
                await status_msg.edit(
                    f"📋 Chapitres trouvés dans:\n\n"
                    f"📹 {original_filename}\n"
                    f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}\n\n"
                    f"{chapters_text}"
                )
                return
                
            elif data == "get_chapter":
                chapters = await videoclient.get_chapters(input_path)
                if not chapters:
                    await status_msg.edit("❌ Aucun chapitre à afficher")
                    return
                
                # Création du clavier de sélection
                keyboard = []
                for i, chap in enumerate(chapters, 1):
                    keyboard.append([KeyboardButton(
                        f"{i}. {chap.get('title', 'Sans titre')[:20]}"
                    )])
                keyboard.append([KeyboardButton("❌ Annuler")])
                
                await status_msg.edit(
                    f"🔢 Sélectionnez le chapitre à afficher:\n\n"
                    f"📹 {original_filename}\n"
                    f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                
                try:
                    response = await client.listen(
                        filters=(filters.text & filters.user(user.id) & ~filters.command),
                        timeout=30
                    )
                    
                    if response.text.strip().lower() in ("❌ annuler", "/cancel"):
                        await status_msg.edit("❌ Opération annulée", reply_markup=ReplyKeyboardRemove())
                        return
                        
                    try:
                        chapter_index = int(response.text.split('.')[0].strip())
                        chapter = chapters[chapter_index-1]
                        
                        await status_msg.edit(
                            f"📌 Chapitre {chapter_index}:\n\n"
                            f"📹 {original_filename}\n"
                            f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}\n\n"
                            f"Titre: {chapter.get('title', 'Sans titre')}\n"
                            f"Début: {chapter['start']}\n"
                            f"Fin: {chapter['end']}",
                            reply_markup=ReplyKeyboardRemove()
                        )
                    except (ValueError, IndexError):
                        await status_msg.edit("❌ Numéro de chapitre invalide", reply_markup=ReplyKeyboardRemove())
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé", reply_markup=ReplyKeyboardRemove())
                return
                
            elif data == "remove_chapters":
                # Suppression des chapitres avec métadonnées
                output_name = f"no_chapters_{int(time.time())}"
                result = await videoclient.remove_chapters(input_path, output_name)
                
                if not result:
                    await status_msg.edit("❌ Échec de la suppression des chapitres")
                    return
                
                # Récupération des infos du résultat
                result_info = await videoclient.get_media_info(result)
                result_width = result_info.width if result_info else width
                result_height = result_info.height if result_info else height
                result_duration = int(result_info.duration) if result_info else duration
                    
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    width=result_width,
                    height=result_height,
                    duration=result_duration,
                    caption=f"🎬 {original_filename} - Sans chapitres",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                
            elif data == "add_chapters":
                # Ajout de chapitres avec interface améliorée
                await status_msg.edit(
                    "📝 Veuillez envoyer le fichier de chapitres (JSON/TXT)...\n\n"
                    f"📹 {original_filename}\n"
                    f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}\n\n"
                    "Formats supportés:\n"
                    "1. JSON: [{'start':'00:00:00','end':'00:01:00','title':'Chapitre 1'},...]\n"
                    "2. Texte: HH:MM:SS Titre (un par ligne)\n\n"
                    "Tapez /cancel pour annuler"
                )
                
                try:
                    chapter_msg = await client.listen(
                        filters=filters.document & filters.user(user.id),
                        timeout=120
                    )
                    
                    chapter_file = await chapter_msg.download(
                        file_name=f"{user_dir}/chapters{Path(chapter_msg.document.file_name).suffix}"
                    )
                    
                    # Validation et parsing des chapitres
                    chapters = []
                    try:
                        if Path(chapter_file).suffix == '.json':
                            with open(chapter_file, 'r', encoding='utf-8') as f:
                                chapters_data = json.load(f)
                            if not isinstance(chapters_data, list):
                                raise ValueError("Format JSON invalide - liste attendue")
                            chapters = chapters_data
                        else:  # Format texte
                            with open(chapter_file, 'r', encoding='utf-8') as f:
                                lines = [line.strip() for line in f if line.strip()]
                            
                            if not lines:
                                raise ValueError("Fichier vide")
                                
                            # Vérifier si c'est le format simple (HH:MM:SS Titre)
                            if ' ' in lines[0]:
                                prev_time = "00:00:00"
                                for i, line in enumerate(lines, 1):
                                    parts = line.split(maxsplit=1)
                                    if len(parts) != 2:
                                        raise ValueError(f"Ligne {i}: format 'HH:MM:SS Titre' attendu")
                                    
                                    current_time = parts[0]
                                    if not re.match(r'^\d{2}:\d{2}:\d{2}$', current_time):
                                        raise ValueError(f"Ligne {i}: format temporel invalide")
                                    
                                    chapters.append({
                                        'start': prev_time,
                                        'end': current_time,
                                        'title': parts[1]
                                    })
                                    prev_time = current_time
                            else:
                                raise ValueError("Format non reconnu")
                    
                    except Exception as e:
                        await status_msg.edit(f"❌ Erreur dans le fichier:\n{str(e)}")
                        return
                    
                    if not chapters:
                        await status_msg.edit("❌ Aucun chapitre valide trouvé")
                        return
                        
                    output_name = f"with_chapters_{int(time.time())}"
                    result = await videoclient.add_chapters(
                        input_path=input_path,
                        output_name=output_name,
                        chapters=chapters
                    )
                    
                    if not result:
                        await status_msg.edit("❌ Échec de l'ajout des chapitres")
                        return
                        
                    # Envoi avec métadonnées
                    result_info = await videoclient.get_media_info(result)
                    result_width = result_info.width if result_info else width
                    result_height = result_info.height if result_info else height
                    result_duration = int(result_info.duration) if result_info else duration
                    
                    await client.send_video(
                        chat_id=user.id,
                        video=result,
                        width=result_width,
                        height=result_height,
                        duration=result_duration,
                        caption=f"🎬 {original_filename} - {len(chapters)} chapitres ajoutés",
                        progress=progress_for_pyrogram,
                        progress_args=("Envoi...", status_msg, time.time())
                    )
                    
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé - opération annulée")
                    return
                    
            elif data == "edit_chapter":
                # Édition avec interface améliorée
                chapters = await videoclient.get_chapters(input_path)
                if not chapters:
                    await status_msg.edit("❌ Aucun chapitre à modifier")
                    return
                
                # Création du clavier de sélection
                keyboard = []
                for i, chap in enumerate(chapters, 1):
                    keyboard.append([KeyboardButton(
                        f"{i}. {chap.get('title', 'Sans titre')[:20]} "
                        f"({chap['start']}-{chap['end']})"
                    )])
                keyboard.append([KeyboardButton("❌ Annuler")])
                
                await status_msg.edit(
                    f"📋 Sélectionnez le chapitre à modifier:\n\n"
                    f"📹 {original_filename}\n"
                    f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                
                try:
                    response = await client.listen(
                        filters=(filters.text & filters.user(user.id) & ~filters.command),
                        timeout=60
                    )
                    
                    if response.text.strip().lower() in ("❌ annuler", "/cancel"):
                        await status_msg.edit("❌ Opération annulée", reply_markup=ReplyKeyboardRemove())
                        return
                        
                    try:
                        chapter_index = int(response.text.split('.')[0].strip())
                        selected_chapter = chapters[chapter_index-1]
                        
                        await status_msg.edit(
                            f"✏️ Modification du chapitre {chapter_index}:\n\n"
                            f"Ancien titre: {selected_chapter.get('title', 'Sans titre')}\n"
                            f"Actuel: {selected_chapter['start']} à {selected_chapter['end']}\n\n"
                            "Envoyez les modifications (1 ligne par champ):\n"
                            "1. Nouveau titre (optionnel)\n"
                            "2. Nouveau début (HH:MM:SS, optionnel)\n"
                            "3. Nouvelle fin (HH:MM:SS, optionnel)",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        edit_data = await client.listen(
                            filters.text & filters.user(user.id),
                            timeout=120
                        )
                        
                        lines = [line.strip() for line in edit_data.text.split('\n') if line.strip()]
                        new_title = lines[0] if len(lines) > 0 else None
                        new_start = lines[1] if len(lines) > 1 else None
                        new_end = lines[2] if len(lines) > 2 else None
                        
                        # Validation des heures si fournies
                        if new_start and not re.match(r'^\d{2}:\d{2}:\d{2}$', new_start):
                            raise ValueError("Format de début invalide")
                        if new_end and not re.match(r'^\d{2}:\d{2}:\d{2}$', new_end):
                            raise ValueError("Format de fin invalide")
                        
                        output_name = f"edited_chapter_{int(time.time())}"
                        result = await videoclient.edit_chapter(
                            input_path=input_path,
                            output_name=output_name,
                            chapter_index=chapter_index,
                            new_title=new_title,
                            new_start=new_start,
                            new_end=new_end
                        )
                        
                        if not result:
                            await status_msg.edit("❌ Échec de la modification")
                            return
                            
                        # Envoi avec métadonnées
                        result_info = await videoclient.get_media_info(result)
                        result_width = result_info.width if result_info else width
                        result_height = result_info.height if result_info else height
                        result_duration = int(result_info.duration) if result_info else duration
                        
                        await client.send_video(
                            chat_id=user.id,
                            video=result,
                            width=result_width,
                            height=result_height,
                            duration=result_duration,
                            caption=f"🎬 {original_filename} - Chapitre {chapter_index} modifié",
                            progress=progress_for_pyrogram,
                            progress_args=("Envoi...", status_msg, time.time())
                        )
                        
                    except (ValueError, IndexError) as e:
                        await status_msg.edit(f"❌ Erreur: {str(e)}", reply_markup=ReplyKeyboardRemove())
                        return
                        
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé", reply_markup=ReplyKeyboardRemove())
                    return
                    
            elif data == "split_chapter":
                # Division avec interface améliorée
                chapters = await videoclient.get_chapters(input_path)
                if not chapters:
                    await status_msg.edit("❌ Aucun chapitre à diviser")
                    return
                
                # Création du clavier de sélection
                keyboard = []
                for i, chap in enumerate(chapters, 1):
                    keyboard.append([KeyboardButton(
                        f"{i}. {chap.get('title', 'Sans titre')[:20]} "
                        f"({chap['start']}-{chap['end']})"
                    )])
                keyboard.append([KeyboardButton("❌ Annuler")])
                
                await status_msg.edit(
                    f"📋 Sélectionnez le chapitre à diviser:\n\n"
                    f"📹 {original_filename}\n"
                    f"📏 {width}x{height} | ⏱ {duration//60}:{duration%60:02d}",
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
                )
                
                try:
                    response = await client.listen(
                        filters=(filters.text & filters.user(user.id) & ~filters.command),
                        timeout=60
                    )
                    
                    if response.text.strip().lower() in ("❌ annuler", "/cancel"):
                        await status_msg.edit("❌ Opération annulée", reply_markup=ReplyKeyboardRemove())
                        return
                        
                    try:
                        chapter_index = int(response.text.split('.')[0].strip())
                        selected_chapter = chapters[chapter_index-1]
                        
                        await status_msg.edit(
                            f"⏱ Division du chapitre {chapter_index}:\n\n"
                            f"Titre: {selected_chapter.get('title', 'Sans titre')}\n"
                            f"Actuel: {selected_chapter['start']} à {selected_chapter['end']}\n\n"
                            "Entrez l'heure de division (HH:MM:SS):",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        split_msg = await client.listen(
                            filters.text & filters.user(user.id),
                            timeout=60
                        )
                        split_time = split_msg.text.strip()
                        
                        if not re.match(r'^\d{2}:\d{2}:\d{2}$', split_time):
                            raise ValueError("Format temporel invalide")
                            
                        output_name = f"split_chapter_{int(time.time())}"
                        result = await videoclient.split_chapter(
                            input_path=input_path,
                            output_name=output_name,
                            chapter_index=chapter_index,
                            split_time=split_time
                        )
                        
                        if not result:
                            await status_msg.edit("❌ Échec de la division")
                            return
                            
                        # Envoi avec métadonnées
                        result_info = await videoclient.get_media_info(result)
                        result_width = result_info.width if result_info else width
                        result_height = result_info.height if result_info else height
                        result_duration = int(result_info.duration) if result_info else duration
                        
                        await client.send_video(
                            chat_id=user.id,
                            video=result,
                            width=result_width,
                            height=result_height,
                            duration=result_duration,
                            caption=f"🎬 {original_filename} - Chapitre {chapter_index} divisé",
                            progress=progress_for_pyrogram,
                            progress_args=("Envoi...", status_msg, time.time())
                        )
                        
                    except (ValueError, IndexError) as e:
                        await status_msg.edit(f"❌ Erreur: {str(e)}", reply_markup=ReplyKeyboardRemove())
                        return
                        
                except asyncio.TimeoutError:
                    await status_msg.edit("⌛ Temps écoulé", reply_markup=ReplyKeyboardRemove())
                    return
            
            await status_msg.edit("✅ Opération terminée avec succès!")
            await asyncio.sleep(2)
            await status_msg.delete()
            
        except Exception as e:
            if status_msg:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
            else:
                await msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            try:
                for file in [locals().get("input_path"), 
                           locals().get("result"), 
                           locals().get("chapter_file")]:
                    if file and os.path.exists(file):
                        try:
                            os.remove(file)
                        except:
                            pass
                
                if os.path.exists(user_dir):
                    shutil.rmtree(user_dir, ignore_errors=True)
            except Exception as e:
                print(f"Erreur de nettoyage: {str(e)}")
    
    elif data == "audio_selection":
        try:
            await callback_query.answer("🔊 Traitement des pistes audio en cours...")
            
            if not msg.reply_to_message or not (msg.reply_to_message.video or 
                                            (msg.reply_to_message.document and 
                                            msg.reply_to_message.document.mime_type.startswith('video/'))):
                await callback_query.answer("❌ Aucun fichier vidéo valide", show_alert=True)
                return

            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            reply_msg = msg.reply_to_message
            
            try:
                try:
                    status_msg = await msg.edit("⏳ Analyse du fichier...")
                except MessageIdInvalid:
                    status_msg = await msg.reply("⏳ Analyse du fichier...")
                
                original_filename = (reply_msg.video.file_name if reply_msg.video 
                                else reply_msg.document.file_name) or "video.mp4"
                input_path = await reply_msg.download(
                    file_name=f"{user_dir}/{original_filename}",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement...", status_msg, time.time())
                )
                
                videoclient = deps.videoclient
                media_info = await videoclient.get_media_info(input_path)
                
                if not media_info or not hasattr(media_info, 'audio_tracks'):
                    await status_msg.edit("❌ Format non supporté ou fichier corrompu")
                    return
                    
                duration = int(media_info.duration) if media_info.duration else 0
                
                if not media_info.audio_tracks:
                    await status_msg.edit("ℹ️ Aucune piste audio détectée")
                    return

                audio_options = []
                for track in media_info.audio_tracks:
                    if not isinstance(track, AudioTrack):
                        continue
                        
                    display_text = (
                        f"{track.language.upper() if track.language else 'INCONNU'} "
                        f"[Piste {track.index}] • "
                        f"{track.codec.name} • "
                        f"{track.channels} canaux • "
                        f"{'DÉFAUT • ' if track.is_default else ''}"
                        f"{track.stream_type}"
                    )
                    
                    audio_options.append({
                        'track': track,
                        'display': display_text
                    })

                if not audio_options:
                    await status_msg.edit("❌ Aucune piste audio valide")
                    return

                keyboard = [
                    [KeyboardButton(opt['display'])] 
                    for opt in audio_options
                ]
                keyboard.append([KeyboardButton("❌ Annuler")])
                
                reply_markup = ReplyKeyboardMarkup(
                    keyboard=keyboard,
                    resize_keyboard=True,
                    one_time_keyboard=True
                )

                try:
                    await status_msg.edit(
                        "🎧 <b>Sélectionnez la piste audio principale</b>\n\n"
                        f"📁 Fichier: {original_filename}\n"
                        f"⏱ Durée: {duration//60}:{duration%60:02d}\n\n"
                        "Pistes disponibles:",
                        reply_markup=reply_markup
                    )
                except MessageIdInvalid:
                    status_msg = await msg.reply(
                        "🎧 <b>Sélectionnez la piste audio principale</b>\n\n"
                        f"📁 Fichier: {original_filename}\n"
                        f"⏱ Durée: {duration//60}:{duration%60:02d}\n\n"
                        "Pistes disponibles:",
                        reply_markup=reply_markup
                    )

                try:
                    response = await client.listen(
                        filters=(filters.text & filters.user(user.id)),
                        timeout=120
                    )
                    
                    if response.text.strip().lower() in ("❌ annuler", "/cancel"):
                        await status_msg.edit("❌ Opération annulée", reply_markup=ReplyKeyboardRemove())
                        return
                        
                    selected_opt = None
                    for opt in audio_options:
                        if opt['display'] == response.text.strip():
                            selected_opt = opt
                            break
                    
                    if not selected_opt:
                        await status_msg.edit("❌ Sélection invalide", reply_markup=ReplyKeyboardRemove())
                        return

                    await response.delete()
                    await status_msg.delete()
                    selected_track = selected_opt['track']
                    
                    try:
                        await status_msg.reply(
                            f"⚙️ Traitement de la piste {selected_track.language or 'inconnu'}...",
                            reply_markup=ReplyKeyboardRemove()
                        )
                    except MessageIdInvalid:
                        status_msg = await msg.reply(
                            f"⚙️ Traitement de la piste {selected_track.language or 'inconnu'}...",
                            reply_markup=ReplyKeyboardRemove()
                        )
                    
                    output_name = f"audio_{selected_track.index}_{int(time.time())}"
                    
                    result = await videoclient.choose_audio(
                        input_path=input_path,
                        output_name=output_name,
                        index=selected_track.index,
                        language=selected_track.language,
                        make_default=True
                    )
                    
                    if not result:
                        await status_msg.reply("❌ Échec du traitement audio")
                        return
                        
                    await client.send_video(
                        chat_id=user.id,
                        video=result,
                        caption=(
                            "🎵 <b>Piste audio sélectionnée</b>\n\n"
                            f"• Langue: {selected_track.language or 'Inconnue'}\n"
                            f"• Codec: {selected_track.codec.name}\n"
                            f"• Canaux: {selected_track.channels}\n"
                            f"• Piste: {selected_track.index}"
                        ),
                        progress=progress_for_pyrogram,
                        progress_args=("Envoi...", status_msg, time.time())
                    )
                    
                    await status_msg.reply("✅ Audio traité avec succès!")
                    await asyncio.sleep(2)
                    await status_msg.delete()
                    
                except asyncio.TimeoutError:
                    await status_msg.reply("⌛ Temps écoulé", reply_markup=ReplyKeyboardRemove())
                except Exception as e:
                    await status_msg.reply(f"❌ Erreur: {str(e)}", reply_markup=ReplyKeyboardRemove())
                    
            except Exception as e:
                await status_msg.reply(f"⚠️ Erreur critique: {str(e)}")
                raise e
                
        finally:
            try:
                if 'input_path' in locals() and os.path.exists(input_path):
                    os.remove(input_path)
                if 'result' in locals() and os.path.exists(result):
                    os.remove(result)
                if os.path.exists(user_dir):
                    shutil.rmtree(user_dir, ignore_errors=True)
            except Exception as e:
                print(f"Erreur de nettoyage: {str(e)}")