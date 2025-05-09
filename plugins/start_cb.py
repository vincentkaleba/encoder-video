import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode
from bot import Dependencies
from data.user import Sex, SubType, User


deps = Dependencies()


@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    """Gère la commande /start et l'inscription des nouveaux utilisateurs"""
    user = message.from_user
    await deps.db.connect()
    
    # Récupérer ou créer l'utilisateur
    user_info = await deps.db.get_user(user.id)
    
    if not user_info:
        # Nouvel utilisateur
        new_user = User(
            uid=user.id,
            fn=user.first_name,
            ln=user.last_name or "",
            un=user.username or ""
        )
        
        try:
            save = await deps.db.save_user(new_user)
            if save:
                fee = await deps.db.update_sub(user.id, SubType.FREE)
                if fee:
                    user_info = await deps.db.get_user(user.id)
            print(f"Nouvel utilisateur enregistré: {user.id}")
        except Exception as e:
            print(f"Erreur création utilisateur {user.id}: {e}")
            await message.reply("❌ Erreur lors de la création de votre profil. Veuillez réessayer.")
            return

    welcome_message = (
        f"<b>👋 Bonjour {user.mention()} !</b>\n\n"
        f"<b>🤖 VideoClient Bot</b> - Solution complète de traitement vidéo\n"
        f"<b>🔹 Abonnement:</b> {user_info.sub.value}\n"
        f"<b>⭐ Points restants:</b> {user_info.tpts}\n\n"
        "<b>⚙️ Fonctionnalités :</b>\n"
        "• Traitement vidéo professionnel\n"
        "• Gestion audio avancée\n"
        "• Manipulation des sous-titres\n\n"
        "<b>📤 Envoyez-moi une vidéo ou utilisez les boutons :</b>"
    )
    
    # Clavier interactif
    buttons = [
        [
            InlineKeyboardButton("📹 Traitement Vidéo", callback_data="video_menu"),
            InlineKeyboardButton("🔊 Gestion Audio", callback_data="audio_menu")
        ],
        [
            InlineKeyboardButton("📝 Sous-titres", callback_data="subtitle_menu"),
            InlineKeyboardButton("📌 Chapitres", callback_data="chapters_menu")
        ],
        [
            InlineKeyboardButton("🛠 Outils", callback_data="tools_menu"),
            InlineKeyboardButton("ℹ️ Infos Média", callback_data="media_info")
        ],
        [InlineKeyboardButton("⚙️ Paramètres", callback_data="settings")],
        [
            InlineKeyboardButton("📚 Documentation", url="https://ffmpeg.org/documentation.html"),
            InlineKeyboardButton("🆘 Aide", callback_data="help")
        ]
    ]
    
    if user_info.sub == SubType.FREE:
        buttons.append([InlineKeyboardButton("💎 Passer Premium", callback_data="upgrade_premium")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    try:
        await message.reply(
            text=welcome_message,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        # Mise à jour activité
        user_info.lst = datetime.datetime.now()
        await deps.db.save_user(user_info)
        
    except Exception as e:
        print(f"Erreur envoi message à {user.id}: {e}")
        await message.reply("❌ Impossible d'afficher l'interface. Veuillez réessayer.")


@Client.on_callback_query(filters.regex("^video_menu$"))
async def video_menu(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔀 Fusion Vidéo", callback_data="video_merge"),
            InlineKeyboardButton("✂️ Découpage", callback_data="video_split")
        ],
        [
            InlineKeyboardButton("📏 Tronquer", callback_data="video_trim"),
            InlineKeyboardButton("✂️ Couper sections", callback_data="video_cut")
        ],
        [
            InlineKeyboardButton("🗜 Compression", callback_data="video_compress"),
            InlineKeyboardButton("🖼 Miniature", callback_data="generate_thumbnail")
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="start_back")]
    ])
    
    menu_description = (
        "<b>🎬 Menu Vidéo</b>\n\n"
        "<pre>"
        "Toutes les fonctionnalités pour manipuler vos vidéos :\n"
        "- Fusionner plusieurs vidéos\n"
        "- Découper en segments\n"
        "- Compresser pour réduire la taille\n"
        "- Générer des miniatures\n"
        "</pre>"
        "\nSélectionnez l'opération souhaitée :"
    )
    
    await callback_query.edit_message_text(
        text=menu_description,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^audio_menu$"))
async def audio_menu(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
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
        [InlineKeyboardButton("🔙 Retour", callback_data="start_back")]
    ])
    
    menu_description = (
        "<b>🔊 Menu Audio</b>\n\n"
        "<pre>"
        "Outils complets pour gérer les pistes audio :\n"
        "- Extraire l'audio des vidéos\n"
        "- Sélectionner des pistes spécifiques\n"
        "- Convertir entre formats audio\n"
        "- Fusionner avec des vidéos\n"
        "</pre>"
        "\nSélectionnez l'opération souhaitée :"
    )
    
    await callback_query.edit_message_text(
        text=menu_description,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^subtitle_menu$"))
async def subtitle_menu(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
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
        [InlineKeyboardButton("🔙 Retour", callback_data="start_back")]
    ])
    
    menu_description = (
        "<b>📝 Menu Sous-titres</b>\n\n"
        "<pre>"
        "Gestion avancée des sous-titres :\n"
        "- Ajouter des sous-titres externes\n"
        "- Extraire les pistes existantes\n"
        "- Sélectionner la langue par défaut\n"
        "- Forcer l'affichage des sous-titres\n"
        "</pre>"
        "\nSélectionnez l'opération souhaitée :"
    )
    
    await callback_query.edit_message_text(
        text=menu_description,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^chapters_menu$"))
async def chapters_menu(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
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
        [InlineKeyboardButton("🔙 Retour", callback_data="start_back")]
    ])
    
    menu_description = (
        "<b>📌 Menu Chapitres</b>\n\n"
        "<pre>"
        "Création et gestion des chapitres :\n"
        "- Ajouter des marqueurs de chapitres\n"
        "- Modifier les chapitres existants\n"
        "- Diviser les longs chapitres\n"
        "- Navigation facile entre sections\n"
        "</pre>"
        "\nSélectionnez l'opération souhaitée :"
    )
    
    await callback_query.edit_message_text(
        text=menu_description,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^tools_menu$"))
async def tools_menu(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Convertir Format", callback_data="convert_format"),
            InlineKeyboardButton("📊 Changer Résolution", callback_data="change_resolution")
        ],
        [
            InlineKeyboardButton("⏱ Changer Durée", callback_data="change_duration"),
            InlineKeyboardButton("🎚 Ajuster Bitrate", callback_data="adjust_bitrate")
        ],
        [
            InlineKeyboardButton("📦 Package Média", callback_data="package_media"),
            InlineKeyboardButton("🔀 Muxer Flux", callback_data="mux_streams")
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="start_back")]
    ])
    
    menu_description = (
        "<b>🛠 Menu Outils</b>\n\n"
        "<pre>"
        "Outils avancés de conversion :\n"
        "- Changer le format des fichiers\n"
        "- Ajuster la résolution vidéo\n"
        "- Modifier la durée des médias\n"
        "- Optimiser le bitrate\n"
        "</pre>"
        "\nSélectionnez l'opération souhaitée :"
    )
    
    await callback_query.edit_message_text(
        text=menu_description,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^media_info$"))
async def media_info(client: Client, callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Infos Vidéo", callback_data="video_info"),
            InlineKeyboardButton("🔊 Infos Audio", callback_data="audio_info")
        ],
        [
            InlineKeyboardButton("📝 Infos Sous-titres", callback_data="subtitle_info"),
            InlineKeyboardButton("📌 Infos Chapitres", callback_data="chapter_info")
        ],
        [InlineKeyboardButton("🔙 Retour", callback_data="start_back")]
    ])
    
    menu_description = (
        "<b>ℹ️ Menu Infos Média</b>\n\n"
        "<pre>"
        "Analyse détaillée des fichiers :\n"
        "- Métadonnées vidéo complètes\n"
        "- Informations sur les pistes audio\n"
        "- Détails des sous-titres inclus\n"
        "- Structure des chapitres\n"
        "</pre>"
        "\nSélectionnez l'opération souhaitée :"
    )
    
    await callback_query.edit_message_text(
        text=menu_description,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("^start_back$"))
async def start_back(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    welcome_message = (
        f"<b>👋 Bonjour {user.mention()} !</b>\n\n"
        "<b>🤖 VideoClient Bot</b> - Solution complète de traitement vidéo avec FFmpeg\n\n"
        "<b>⚙️ Fonctionnalités principales :</b>\n"
        "• Traitement vidéo professionnel\n"
        "• Gestion audio avancée\n"
        "• Manipulation des sous-titres\n"
        "• Chapitrage et métadonnées\n\n"
        "<b>📤 Envoyez-moi une vidéo ou utilisez les boutons ci-dessous :</b>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📹 Traitement Vidéo", callback_data="video_menu"),
            InlineKeyboardButton("🔊 Gestion Audio", callback_data="audio_menu")
        ],
        [
            InlineKeyboardButton("📝 Sous-titres", callback_data="subtitle_menu"),
            InlineKeyboardButton("📌 Chapitres", callback_data="chapters_menu")
        ],
        [
            InlineKeyboardButton("🛠 Outils", callback_data="tools_menu"),
            InlineKeyboardButton("ℹ️ Infos Média", callback_data="media_info")
        ],
        [InlineKeyboardButton("⚙️ Paramètres", callback_data="settings")],
        [
            InlineKeyboardButton("📚 Documentation", url="https://ffmpeg.org/documentation.html"),
            InlineKeyboardButton("🆘 Aide", callback_data="help")
        ]
    ])
    
    await callback_query.edit_message_text(
        text=welcome_message,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )