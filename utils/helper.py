import math
import time
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

PROGRESS_BAR_TEMPLATE = """<b>
╭━━━━━━━━━━━━━━━⪼
┃ 📦 Fichier : {current_size} / {total_size}
┃ 📈 Progression : {progress}%
┃ ⚡ Vitesse : {speed}/s
┃ ⏳ Temps restant : {eta}
╰━━━━━━━━━━━━━━━⪼
</b>"""

async def progress_for_pyrogram(current: int, total: int, ud_type: str, message, start_time: float, progress_id: str = None):
    now = time.time()
    diff = now - start_time
    if round(diff % 5.0) == 0 or current == total:
        try:
            percentage = current * 100 / total
            speed = current / diff
            elapsed_time_ms = round(diff) * 1000
            time_to_completion_ms = round((total - current) / speed) * 1000
            estimated_total_time = elapsed_time_ms + time_to_completion_ms

            eta_str = format_time(estimated_total_time)

            progress_bar = generate_progress_bar(percentage)

            progress_text = PROGRESS_BAR_TEMPLATE.format(
                current_size=human_readable_size(current),
                total_size=human_readable_size(total),
                progress=round(percentage, 2),
                speed=human_readable_size(speed),
                eta=eta_str if eta_str else "0 s"
            )

            await message.edit_text(
                text=f"{ud_type}\n\n{progress_bar}\n\n{progress_text}",
            )
        except Exception as e:
            # print(f"Erreur lors de la mise à jour de la progression : {e}")
            pass

def human_readable_size(size: int) -> str:
    if size is None or size == 0:
        return "0 B"
    power = 2**10
    n = 0
    dic_powerN = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {dic_powerN[n]}B"

def format_time(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days: parts.append(f"{days}ᴅ")
    if hours: parts.append(f"{hours}ʜ")
    if minutes: parts.append(f"{minutes}ᴍ")
    if seconds: parts.append(f"{seconds}ꜱ")
    if milliseconds: parts.append(f"{milliseconds}ᴍꜱ")

    return ", ".join(parts)

def convert(seconds: int) -> str:
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{hour}:{minutes:02}:{seconds:02}"

def generate_progress_bar(percentage: float) -> str:
    filled = "⬢" * math.floor(percentage / 5)
    empty = "⬡" * (20 - math.floor(percentage / 5))
    return filled + empty

def convert_to_seconds(time_str: str) -> float:
    """
    Convertit une chaîne de format HH:MM:SS ou MM:SS en secondes.

    Args:
        time_str (str): Le temps sous forme de chaîne (par exemple '00:01:30' ou '01:30').

    Returns:
        float: Le temps en secondes.
    """
    parts = time_str.split(":")
    if len(parts) == 3:  # Format HH:MM:SS
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:  # Format MM:SS
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    else:
        raise ValueError("Format de temps invalide")

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