import asyncio
import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageIdInvalid
from bot import Dependencies
from utils.videoclient import AudioCodec, VideoClient
from utils.helper import convert_to_seconds, progress_for_pyrogram
from pathlib import Path
import humanize

deps = Dependencies()
users_operations = {}


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗜 Compresser", callback_data="compress"),
            InlineKeyboardButton("✂️ Découper", callback_data="cut")
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
            InlineKeyboardButton("✂️ Découpe", callback_data="cut")
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

@Client.on_message(filters.document | filters.video)
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
                        
                        asyncio.sleep(3)
                        
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
    
    
    # elif data == "video_merge":