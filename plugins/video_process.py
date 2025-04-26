from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗜 Compresser", callback_data="compress"),
            InlineKeyboardButton("✂️ Découper", callback_data="cut")
        ],
        [
            InlineKeyboardButton("🎵 Audio", callback_data="audio_menu"),
            InlineKeyboardButton("📝 Sous-titres", callback_data="subs_menu")
        ],
        [
            InlineKeyboardButton("🛠 Outils", callback_data="tools_menu"),
            InlineKeyboardButton("ℹ️ Infos", callback_data="info_menu")
        ],
        [
            InlineKeyboardButton("⚙️ Paramètres", callback_data="settings"),
            InlineKeyboardButton("❌ Fermer", callback_data="close")
        ]
    ])

def audio_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Extraire Audio", callback_data="extract_audio"),
            InlineKeyboardButton("🔊 Sélection Piste", callback_data="select_audio")
        ],
        [
            InlineKeyboardButton("🌐 Langue Audio", callback_data="audio_lang"),
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def subs_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Ajouter ST", callback_data="add_sub"),
            InlineKeyboardButton("📤 Extraire ST", callback_data="extract_sub")
        ],
        [
            InlineKeyboardButton("👁 Sélection ST", callback_data="select_sub"),
            InlineKeyboardButton("🔙 Retour", callback_data="main_menu")
        ]
    ])

def tools_menu():
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
    
    if data == "main_menu":
        await callback_query.edit_message_text(
            "🔧 Sélectionnez une opération :",
            reply_markup=main_menu()
        )
    elif data == "audio_menu":
        await callback_query.edit_message_text(
            "🔊 Menu Audio :",
            reply_markup=audio_menu()
        )
    elif data == "subs_menu":
        await callback_query.edit_message_text(
            "📝 Menu Sous-titres :",
            reply_markup=subs_menu()
        )
    elif data == "tools_menu":
        await callback_query.edit_message_text(
            "🛠 Outils avancés :",
            reply_markup=tools_menu()
        )
    elif data == "info_menu":
        await callback_query.edit_message_text(
            "ℹ️ Informations :",
            reply_markup=info_menu()
        )
    elif data == "close":
        await callback_query.message.delete()
    
    await callback_query.answer()