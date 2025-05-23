# VideoClient Encoder, Converter, and Subtitler with FFmpeg

## 🖊️ Description
`VideoClient` est une classe Python permettant de traiter, modifier et gérer des fichiers vidéo et audio via FFmpeg.

---

## ✶ Installation

### 1. Installer FFmpeg
Assurez-vous que `ffmpeg` est installé et accessible dans votre `PATH`.

- **Linux / MacOS** :
```bash
sudo apt update && sudo apt install ffmpeg
```

- **Windows** :
[Télécharger FFmpeg](https://ffmpeg.org/download.html) et ajouter son chemin à la variable d'environnement `PATH`.

### 2. Installer les dépendances Python

Créer un environnement virtuel (optionnel mais recommandé) :
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate    # Windows
```

Installer les requirements :
```bash
pip install -r requirements.txt
```

#### Contenu de `requirements.txt`
```text
loguru
```

---

## ✶ Initialisation

```python
VideoClient(name: str, out_pth: str, trd: int = 5, ffmpeg: str = "ffmpeg")
```

**Paramètres :**
- `name` : Nom de l'instance.
- `out_pth` : Répertoire de sortie pour les fichiers traités.
- `trd` : Nombre de threads (par défaut : 5).
- `ffmpeg` : Chemin vers l'exécutable ffmpeg (par défaut : "ffmpeg").

---

## ✶ Méthodes principales

| Méthode                      | Description                                        | Paramètres Clés                   | Retour            |
|------------------------------|----------------------------------------------------|-----------------------------------|-------------------|
| `__init__()`                 | Initialise le client vidéo                         | `name`, `out_pth`, `trd`, `ffmpeg`| -                 |
| `_handle_shutdown()`         | Gère l'arrêt du client                             | -                                 | -                 |
| `_register_signal_handlers()`| Enregistre les gestionnaires de signaux            | -                                 | -                 |
| `_run_ffmpeg_command()`      | Exécute une commande FFmpeg                        | `command`, `timeout`              | `bool`            |
| `_setup_logger()`            | Configure le logger interne                        | -                                 | `logging.Logger`  |
| `_verify_ffmpeg()`           | Vérifie que FFmpeg est installé et utilisable      | -                                 | -                 |

---

## ✶ Opérations Vidéo

| Méthode                        | Description                                                   | Paramètres Clés                                                       | Retour                    |
|--------------------------------|---------------------------------------------------------------|-----------------------------------------------------------------------|---------------------------|
| `add_chapters()`               | Ajoute des chapitres à un fichier vidéo/audio                 | `input_path`, `output_name`, `chapters`                                | `Path`                    |
| `concat_video()`               | Concatène plusieurs vidéos                                    | `input_paths`, `output_name`, `output_format`, `transition_duration`   | `Path`                    |
| `compress_video()`             | Compresse en plusieurs résolutions et formats                 | `input_path`, `output_basename`, `target_formats`, `keep_original_quality` | `Dict[str, List[Path]]`   |
| `cut_video()`                  | Coupe des segments dans la vidéo                              | `input_path`, `output_name`, `cut_ranges`                             | `Path`                    |
| `edit_chapter()`               | Modifie un chapitre existant                                  | `input_path`, `output_name`, `chapter_index`, `new_start`, `new_end`, `new_title` | `Path`                    |
| `generate_thumbnail()`         | Crée une miniature à partir de la vidéo                       | `input_path`, `output_name`, `time_offset`, `width`                   | `Path`                    |
| `get_chapter()`                | Récupère un chapitre spécifique                               | `input_path`, `chapter_index`                                        | `Dict`                    |
| `get_chapters()`               | Liste tous les chapitres du média                             | `input_path`                                                         | `List[Dict]`              |
| `get_media_info()`             | Extrait les métadonnées via FFprobe                           | `file_path`                                                          | `MediaFileInfo`           |
| `remove_chapters()`            | Supprime tous les chapitres                                    | `input_path`, `output_name`                                          | `Path`                    |
| `split_chapter()`              | Divise un chapitre en deux                                     | `input_path`, `output_name`, `chapter_index`, `split_time`           | `Path`                    |
| `trim_video()`                 | Découpe la vidéo entre deux temps                             | `input_path`, `output_name`, `start_time`, `end_time`                | `Path`                    |

---

## ✶ Gestion Audio

| Méthode                 | Description                                      | Paramètres Clés                                  | Retour  |
|-------------------------|--------------------------------------------------|--------------------------------------------------|---------|
| `choose_audio()`        | Sélectionne une piste audio spécifique           | `input_path`, `output_name`, `language`, `index`, `make_default` | `Path` |
| `convert_audio()`       | Convertit l'audio dans un format donné           | `input_path`, `output_name`, `codec`, `bitrate`   | `Path` |
| `extract_audio()`       | Extrait l'audio de la vidéo                      | `input_path`, `output_name`, `codec`, `bitrate`   | `Path` |
| `merge_video_audio()`   | Fusionne une vidéo et une piste audio             | `video_path`, `audio_path`, `output_name`         | `Path` |
| `remove_audio()`        | Supprime l'audio de la vidéo                      | `input_path`, `output_name`                       | `Path` |

---

## ✶ Sous-titres

| Méthode                  | Description                                      | Paramètres Clés                        | Retour       |
|--------------------------|--------------------------------------------------|----------------------------------------|--------------|
| `add_subtitle()`         | Ajoute une piste de sous-titres                  | `sbt_file`, `input_path`, `output_name`, `language`, `index`, `is_default`, `is_forced` | `Path` |
| `choose_subtitle()`      | Sélectionne une piste de sous-titres             | `input_path`, `output_name`, `language`, `index`, `make_default` | `Path` |
| `extract_subtitles()`    | Extrait toutes les pistes de sous-titres         | `input_path`, `output_dir`               | `List[Path]` |
| `remove_subtitles()`     | Supprime toutes les pistes de sous-titres         | `input_path`, `output_name`               | `Path`       |

---

## ✶ Contrôle

| Méthode | Description                       | Paramètres | Retour |
|---------|-----------------------------------|------------|--------|
| `stop()`| Arrête le client proprement       | -          | -      |

---

## ✶ Exemple d'utilisation

```python
client = VideoClient(name="MyClient", out_pth="outputs/")

# Ajouter des chapitres
client.add_chapters(
    input_path="input.mp4",
    output_name="output_with_chapters",
    chapters=[
        {"start": "00:00:00", "end": "00:05:00", "title": "Introduction"},
        {"start": "00:05:01", "end": "00:10:00", "title": "Partie 1"}
    ]
)

# Ajouter un sous-titre
client.add_subtitle(
    sbt_file="subtitle.srt",
    input_path="input.mp4",
    output_name="output_with_subtitle",
    language="fre",
    index=0,
    is_default=True,
    is_forced=False
)
```

---

## ✶ Requirements
- Python 3.7+
- FFmpeg installé et accessible via la variable d'environnement `PATH`.
- Loguru pour le logging.

---

## 🔗 Liens utiles
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Python Signal Module](https://docs.python.org/3/library/signal.html)
- [Python Asyncio Subprocess](https://docs.python.org/3/library/asyncio-subprocess.html)

---

> © 2025 - VideoClient by Hyoshcode Dev