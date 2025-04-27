import asyncio
import os
import time
from typing import Dict
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageIdInvalid
from bot import Dependencies
from utils.videoclient import AudioCodec, MediaType, VideoClient
from utils.helper import convert_to_seconds, progress_for_pyrogram
from pathlib import Path
import humanize

deps = Dependencies()
users_operations: Dict[int, dict] = {}


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
            InlineKeyboardButton("🛠 Outils", callback_data="tools_menu1"),
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
            InlineKeyboardButton("🌐 Langue Sous-titres", callback_data="subtitle_language"),
            InlineKeyboardButton("🏷 Forcer Sous-titres", callback_data="force_subtitle")
        ],
        [
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def tools_menu1():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Convertir", callback_data="convert"),
            InlineKeyboardButton("⏱ Tronquer", callback_data="trim")
        ],
        [
            InlineKeyboardButton("🖼 Miniature", callback_data="thumbnail"),
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def info_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("All Info", callback_data="all_info"),
            InlineKeyboardButton("📌 Chapitres", callback_data="chapters"),
            InlineKeyboardButton("ℹ️ Métadonnées", callback_data="metadata")
        ],
        [
            InlineKeyboardButton("📊 Résolution", callback_data="resolution"),
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

@Client.on_message(filters.document | filters.video | filters.audio | filters.voice | filters.animation)
async def handle_video(client: Client, message: Message):
    if message.document or message.video:
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
        
        await status_msg.edit("⚙️ Compression en cours...")
        try:
            videoclient = deps.videoclient
            videoclient.output_path = Path(user_dir)
            
            result = await videoclient.compress_video(
                input_path=file_path,
                output_basename="compressed",
                target_formats=["mp4"],
                keep_original_quality=False,
            )
            
            # Envoi des fichiers résultants
            if "mp4" in result and result["mp4"]:
                for output_file in result["mp4"]:
                    if os.path.exists(output_file):
                        await client.send_video(
                            chat_id=user.id,
                            video=output_file,
                            caption=f"📦 Fichier compressé : {os.path.basename(output_file)}",
                            progress=progress_for_pyrogram,
                            progress_args=("Envoi...", status_msg, time.time())
                        )
                        await asyncio.sleep(3)
                        try:
                            os.remove(output_file)
                        except:
                            pass
            
            await status_msg.delete()
            
        except Exception as e:
            await status_msg.edit(f"❌ Erreur de compression: {str(e)}")
        
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(user_dir):
                os.rmdir(user_dir)
        except Exception as e:
            print(f"Erreur de nettoyage: {str(e)}")
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
                print(f"Erreur de nettoyage: {str(e)}")


    elif data == "close":
        await callback_query.message.delete()
    
    elif data == "cut":
        try:
            await callback_query.answer("⏳ Découpage en préparation...")
            
            # Vérification du fichier source
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Aucun fichier vidéo trouvé", show_alert=True)
                return
            
            # Création du dossier utilisateur
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            ext = None
            
            # Téléchargement du fichier
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
                ext = file_path.split(".")[-1]
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de téléchargement: {str(e)}")
                try:
                    os.rmdir(user_dir)
                except:
                    pass
                return

            cut_instructions = (
                "✂️ <b>Format attendu</b> : <code>HH:MM:SS-HH:MM:SS,HH:MM:SS-HH:MM:SS,...</code>\n"
                "Par exemple :\n"
                "<code>00:01:30-00:02:45,00:03:00-00:04:15</code> pour deux séquences\n\n"
                "Envoyez maintenant les temps de découpage séparés par des virgules :"
            )
            
            cut_time_msg = await status_msg.edit(cut_instructions)
            
            try:
                # Attente de la réponse utilisateur
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
                        if len(parts) == 3: 
                            return True
                        elif len(parts) == 2: 
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
                
                await status_msg.edit("⚙️ Découpage en cours...")
                
                result = await videoclient.cut_video(
                    input_path=file_path,
                    output_name="cut",
                    cut_ranges=cut_ranges, 
                )
                
                # Envoi des résultats
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    caption=f"📦 Vidéo découpée ({len(cut_ranges)} plage(s)) : {os.path.basename(result)}",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                await asyncio.sleep(3)
                try:
                    os.remove(result)
                except:
                    pass
                
                await status_msg.delete()
                
            except Exception as e:
                await status_msg.edit(f"❌ Erreur de découpage: {str(e)}")
                
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
                    reply_markup=main_menu(),
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

            trim_instructions = (
                "✂️ <b>Format attendu</b> : <code>HH:MM:SS-HH:MM:SS</code>\n"
                "Par exemple :\n"
                "<code>00:01:30-00:02:45</code> pour une séquence\n\n"
                "Envoyez maintenant le temps de découpage :"
            )
            
            await status_msg.edit(trim_instructions)
            
            try:
                # Attente de la réponse utilisateur
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
                    
                await status_msg.edit(f"✂️ Découpage de {start_time_str} à {end_time_str}...")
                
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.trim_video(
                    input_path=file_path,
                    output_name="trimmed",
                    start_time=start_time,
                    end_time=end_time
                )
                
                if not result:
                    await status_msg.edit("❌ Échec du découpage vidéo")
                    return
                    
                # Envoi du résultat
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    caption=f"✂️ Vidéo découpée: {start_time_str} à {end_time_str}",
                    progress=progress_for_pyrogram,
                    progress_args=("Envoi...", status_msg, time.time())
                )
                
                await status_msg.edit("✅ Découpage terminé avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
                
            except asyncio.TimeoutError:
                await status_msg.edit("❌ Temps écoulé (120s)")
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
    
    
    elif data == "video_merge":
        try:
            await callback_query.answer("⏳ Fusion vidéo en préparation...")
            
            # Vérifier qu'on a au moins une vidéo dans le message reply
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Répondez à une vidéo pour commencer", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la première vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la première vidéo...")
            
            # Télécharger la première vidéo (celle à laquelle on a répondu)
            try:
                first_video_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/video_0.mp4",
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

            # Stocker les infos temporaires
            users_operations[user.id] = {
                'dir': user_dir,
                'video_paths': [first_video_path],
                'status_msg': status_msg
            }
            
            # Demander les vidéos supplémentaires
            await status_msg.edit(
                "📹 <b>Fusion vidéo</b>\n\n"
                f"1. {os.path.basename(first_video_path)} (vidéo de départ)\n\n"
                "Envoyez maintenant les autres vidéos à fusionner (une par message)\n\n"
                "Tapez /done quand vous avez terminé\n"
                "Tapez /cancel pour annuler"
            )
            
            # Écouter les nouvelles vidéos
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
                    
                    # Télécharger la nouvelle vidéo
                    try:
                        video_num = len(users_operations[user.id]['video_paths'])
                        new_video_path = await response.download(
                            file_name=f"{user_dir}/video_{video_num}.mp4",
                            progress=progress_for_pyrogram,
                            progress_args=(f"Téléchargement vidéo {video_num+1}...", status_msg, time.time())
                        )
                        users_operations[user.id]['video_paths'].append(new_video_path)
                        
                        await response.delete()
                        
                        video_list = "\n".join(
                            f"{i+1}. {os.path.basename(p)}"
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

            await status_msg.edit(
                    "🛠 <b>Choisissez l'extension de sorti :</b>\n\n"
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
                
                # Demander la durée de transition
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
                # Lancer la fusion
                await status_msg.edit("⚙️ Fusion des vidéos en cours...")
                
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.concat_video(
                    input_paths=users_operations[user.id]['video_paths'],
                    output_name="merged",
                    output_format=output_format,
                    transition_duration=transition_duration
                )
                
                if not result:
                    await status_msg.edit("❌ Échec de la fusion des vidéos")
                    return
                    
                # Envoyer le résultat
                await client.send_video(
                    chat_id=user.id,
                    video=result,
                    caption=f"📼 Vidéo fusionnée ({len(users_operations[user.id]['video_paths'])} clips)",
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
            # Nettoyage
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

            cut_instructions = (
                "✂️ <b>Format attendu</b> : <code>HH:MM:SS-HH:MM:SS,HH:MM:SS-HH:MM:SS,...</code>\n"
                "Par exemple :\n"
                "<code>00:01:30-00:02:45,00:03:00-00:04:00</code> pour plusieurs séquences\n\n"
                "Envoyez maintenant les plages de découpage :"
            )
            
            await status_msg.edit(cut_instructions)
            
            try:
                # Attente de la réponse utilisateur
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=120
                )
                cut_ranges = response.text.strip().split(",")
                cut_ranges = [r.split("-") for r in cut_ranges]
                cut_ranges = [(convert_to_seconds(r[0]), convert_to_seconds(r[1])) for r in cut_ranges]
                await response.delete()
                # Vérification des plages de découpage
                for start_time, end_time in cut_ranges:
                    if start_time >= end_time:
                        await status_msg.edit("❌ Le temps de fin doit être après le temps de début")
                        return
                await status_msg.edit(f"✂️ Découpage des vidéos...")
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                # Découpage vidéo
                result = await videoclient.split_video(
                    input_path=file_path,
                    output_name="split",
                    cut_ranges=cut_ranges
                )
                if not result:
                    await status_msg.edit("❌ Échec du découpage vidéo")
                    return
                # Envoi des résultats
                for i, video_path in enumerate(result):
                    await client.send_video(
                        chat_id=user.id,
                        video=video_path,
                        caption=f"✂️ Vidéo découpée {i+1}/{len(result)}",
                        progress=progress_for_pyrogram,
                        progress_args=(f"Envoi vidéo {i+1}...", status_msg, time.time())
                    )
                await status_msg.edit("✅ Découpage terminé avec succès!")
                await asyncio.sleep(2)
                await status_msg.delete()
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
            except Exception as e:
                await status_msg.edit(f"❌ Erreur: {str(e)}")
        finally:
            # Nettoyage
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
                try:
                    del users_operations[user.id]
                except KeyError:
                    pass
                try:
                    if os.path.exists(user_dir):
                        os.rmdir(user_dir)
                except:
                    pass
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
                try:
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
            
            # Vérifier que l'utilisateur a répondu à une vidéo
            if not msg.reply_to_message or not (msg.reply_to_message.video or msg.reply_to_message.document):
                await callback_query.answer("❌ Répondez à une vidéo", show_alert=True)
                return
            
            user_dir = f"downloads/{user.id}_{int(time.time())}"
            os.makedirs(user_dir, exist_ok=True)
            
            try:
                status_msg = await msg.edit("⏳ Téléchargement de la vidéo...")
            except MessageIdInvalid:
                status_msg = await msg.reply("⏳ Téléchargement de la vidéo...")
            
            # Télécharger la vidéo
            try:
                video_path = await msg.reply_to_message.download(
                    file_name=f"{user_dir}/video_source.mp4",
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

            # Demander le fichier audio
            await status_msg.edit(
                "🎵 <b>Maintenant envoyez le fichier audio</b>\n\n"
                "Format supporté: MP3, AAC, WAV\n\n"
                "Tapez /cancel pour annuler"
            )
            
            try:
                # Attendre le fichier audio
                audio_response = await client.listen(
                    filters=(filters.audio | filters.document | filters.text) & filters.user(user.id),
                    timeout=120
                )
                
                if audio_response.text and "/cancel" in audio_response.text:
                    await status_msg.edit("❌ Fusion annulée")
                    return
                
                # Télécharger l'audio
                await status_msg.edit("⏳ Téléchargement de l'audio...")
                audio_path = await audio_response.download(
                    file_name=f"{user_dir}/audio_source.mp3",
                    progress=progress_for_pyrogram,
                    progress_args=("Téléchargement audio...", status_msg, time.time())
                )
                
                await audio_response.delete()
                # Lancer la fusion
                await status_msg.edit("⚙️ Fusion vidéo/audio en cours...")
                
                videoclient = deps.videoclient
                videoclient.output_path = Path(user_dir)
                
                result = await videoclient.merge_video_audio(
                    video_path=video_path,
                    audio_path=audio_path,
                    output_name="merged"
                )
                
                if not result:
                    await status_msg.edit("❌ Échec de la fusion")
                    return
                    
                # Envoyer le résultat
                await client.send_video(
                    chat_id=user.id,
                    video=result,
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
            # Nettoyage
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

            await status_msg.edit(
                "🔇 <b>Supprimer l'audio de cette vidéo?</b>\n\n"
                f"Fichier: {os.path.basename(input_path)}"
                "\n\nEtes-vous sûr de vouloir continuer?\n\n"
                "Tapez /cancel pour annuler, /done pour confirmer"
            )
            
            try:
                # Attendre la confirmation
                response = await client.listen(
                    filters.text & filters.user(user.id),
                    timeout=60
                )
                
                if response.text.strip().lower() == "/cancel":
                    await status_msg.edit("❌ Opération annulée")
                    return
                elif response.text.strip().lower() != "/done":
                    await status_msg.edit("❌ Réponse invalide. Tapez /done pour confirmer ou /cancel pour annuler.")
                    return
                    
            except asyncio.TimeoutError:
                await status_msg.edit("⌛ Temps écoulé - opération annulée")
                return

            await response.delete()
            # Traitement de la vidéo
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

            await client.send_document( 
                chat_id=user.id,
                document=result,
                caption="🎬 Vidéo sans audio",
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
            # Nettoyage complet
            try:
                if os.path.exists(input_path):
                    os.remove(input_path)
                if 'result' in locals() and os.path.exists(result):
                    os.remove(result)
                if os.path.exists(user_dir):
                    for root, _, files in os.walk(user_dir):
                        for file in files:
                            try:
                                os.remove(os.path.join(root, file))
                            except:
                                pass
                    os.rmdir(user_dir)
            except Exception as e:
                print(f"Erreur de nettoyage: {str(e)}")