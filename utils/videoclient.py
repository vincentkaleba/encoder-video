import asyncio
import asyncio.subprocess as aio_subproc
from collections import defaultdict
import re
import subprocess
import shlex
import json
import logging
import logging.handlers
import signal
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, List, Dict, Tuple, Union, Iterator

# Optional imports (used when available)
try:
    import psutil
except Exception:
    psutil = None


class MediaType(Enum):
    MP4 = "mp4"
    MKV = "mkv"
    MKA = "mka"
    AVI = "avi"
    MOV = "mov"
    WEBM = "webm"
    MP3 = "mp3"
    AAC = "aac"
    OGG = "ogg"

    @classmethod
    def from_extension(cls, ext: str) -> Optional['MediaType']:
        ext = ext.lower().lstrip('.')
        for member in cls:
            if member.value == ext:
                return member
        return None


class AudioCodec(Enum):
    AAC = "aac"
    AC3 = "ac3"
    EAC3 = "eac3"
    DTS = "dts"
    MP3 = "mp3"
    OPUS = "opus"
    VORBIS = "vorbis"


class SubtitleCodec(Enum):
    SRT = "srt"
    ASS = "ass"
    SSA = "ssa"
    MOV_TEXT = "mov_text"
    VOBSUB = "vobsub"
    PGS = "pgs"
    TX3G = "tx3g"
    WEBVTT = "webvtt"
    TEXT = "text"
    SUBRIP = "subrip"

    @property
    def extension(self) -> str:
        # Map logical codec -> reasonable file extension for extraction
        mapping = {
            SubtitleCodec.SRT: "srt",
            SubtitleCodec.ASS: "ass",
            SubtitleCodec.SSA: "ssa",
            SubtitleCodec.MOV_TEXT: "ttxt",
            SubtitleCodec.VOBSUB: "sub",   # vobsub often yields .sub/.idx, use .sub as default
            SubtitleCodec.PGS: "sup",      # PGS often stored as .sup
            SubtitleCodec.TX3G: "tx3g",
            SubtitleCodec.WEBVTT: "vtt",
            SubtitleCodec.TEXT: "txt",
            SubtitleCodec.SUBRIP: "srt"
        }
        return mapping.get(self, self.name.lower())


@dataclass
class SubtitleTrack:
    # `stream_index` is the global ffprobe stream index (use for -map)
    stream_index: int
    language: str
    codec: SubtitleCodec
    is_default: bool = False
    is_forced: bool = False
    stream_type: str = "text"  # 'text' or 'graphic'
    container_attachment_index: Optional[int] = None  # if came from an attachment

    def __str__(self) -> str:
        flags = []
        if self.is_default:
            flags.append("default")
        if self.is_forced:
            flags.append("forced")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        return f"Subtitle stream {self.stream_index}: {self.language} [{self.codec}]{flag_str} type={self.stream_type}"


@dataclass
class AudioTrack:
    # `stream_index` is the global ffprobe stream index (use for -map)
    stream_index: int
    language: str
    codec: Optional[AudioCodec] = None
    channels: int = 2
    is_default: bool = False

    def __str__(self) -> str:
        return f"Audio stream {self.stream_index}: {self.language} [{self.codec}] {self.channels}ch"


@dataclass
class MediaFileInfo:
    path: Path
    size: int
    duration: float
    media_type: MediaType
    width: int = 0
    height: int = 0
    bitrate: int = 0
    audio_tracks: List[AudioTrack] = field(default_factory=list)
    subtitle_tracks: List[SubtitleTrack] = field(default_factory=list)
    attachments: List[Dict] = field(default_factory=list)  # list of {index, filename, mime_type}

    def add_audio_track(self, t: AudioTrack):
        self.audio_tracks.append(t)

    def add_subtitle_track(self, t: SubtitleTrack):
        self.subtitle_tracks.append(t)


class VideoClient:
    __slots__ = ('name', 'output_path', 'thread_count', 'ffmpeg_path', 'ffprobe_path',
                 'executor', 'logger', 'running', '_ffmpeg_version', '_ffprobe_version')

    def __init__(self, name: str, out_pth: Union[str, Path], trd: int = 4,
                 ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        self.name = name
        self.output_path = Path(out_pth)
        self.thread_count = max(1, min(trd, 32))
        self.ffmpeg_path = ffmpeg
        self.ffprobe_path = ffprobe
        self.running = False
        self._ffmpeg_version = None
        self._ffprobe_version = None

        self._setup_output_dir()
        self.logger = self._setup_logger()
        self._verify_ffmpeg()
        self._verify_ffprobe()
        self.executor = ThreadPoolExecutor(max_workers=self.thread_count)
        self._register_signal_handlers()

    def _setup_output_dir(self):
        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Could not create output directory: {e}")

    def _setup_logger(self):
        logger = logging.getLogger(f"VideoClient_{hash(self.name)}")
        if logger.handlers:
            return logger
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        try:
            fh = logging.handlers.RotatingFileHandler(self.output_path / f"{self.name}.log",
                                                      maxBytes=5 * 1024 * 1024, backupCount=2)
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception:
            logger.warning("Could not enable file logging")
        return logger

    def _verify_ffprobe(self):
        try:
            res = subprocess.run([self.ffprobe_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, timeout=5, check=True)
            self._ffprobe_version = res.stdout.splitlines()[0]
            self.logger.info(f"ffprobe: {self._ffprobe_version}")
        except Exception as e:
            raise RuntimeError(f"ffprobe not available: {e}")

    def _verify_ffmpeg(self):
        try:
            res = subprocess.run([self.ffmpeg_path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, timeout=5, check=True)
            self._ffmpeg_version = res.stdout.splitlines()[0]
            self.logger.info(f"ffmpeg: {self._ffmpeg_version}")
        except Exception as e:
            raise RuntimeError(f"ffmpeg not available: {e}")

    def _register_signal_handlers(self):
        try:
            signal.signal(signal.SIGINT, self._handle_shutdown)
            signal.signal(signal.SIGTERM, self._handle_shutdown)
        except Exception:
            pass

    def _handle_shutdown(self, signum, frame):
        self.logger.info(f"Shutdown signal {signum}")
        self.stop()

    def start(self):
        if self.running:
            return
        self.running = True
        self.logger.info("VideoClient started")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.logger.info("VideoClient stopped")

    async def _run_ffmpeg_command(self, command: List[str], timeout: int = 600) -> bool:
        """
        Runs ffmpeg/ffprobe command asynchronously.
        Returns True on success (exit 0), False otherwise.
        """
        if not self.running:
            # For convenience allow running commands even if not explicitly started:
            self.logger.debug("VideoClient not 'started' — running command anyway")

        self.logger.debug("Running command: " + " ".join(shlex.quote(x) for x in command))
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # optional memory monitoring
            async def monitor():
                if psutil is None:
                    return
                try:
                    p = psutil.Process(proc.pid)
                    while True:
                        if proc.returncode is not None:
                            break
                        mem = p.memory_info().rss // 1024 // 1024
                        self.logger.debug(f"ffmpeg pid={proc.pid} mem={mem}MB")
                        await asyncio.sleep(3)
                except Exception:
                    return

            mon_task = asyncio.create_task(monitor())

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            finally:
                mon_task.cancel()

            if proc.returncode != 0:
                err = stderr.decode(errors='ignore').strip() or stdout.decode(errors='ignore').strip()
                self.logger.debug(f"Command failed (code {proc.returncode}): {err[:800]}")
                return False

            self.logger.debug("Command succeeded")
            return True

        except asyncio.TimeoutError:
            self.logger.warning(f"Command timed out ({timeout}s)")
            try:
                proc.kill()
            except Exception:
                pass
            return False
        except FileNotFoundError:
            self.logger.error("Executable not found (check ffmpeg/ffprobe path)")
            return False
        except Exception as e:
            self.logger.error(f"Command exception: {e}", exc_info=True)
            return False

    async def get_media_info(self, file_path: Union[str, Path]) -> Optional[MediaFileInfo]:
        path = Path(file_path)
        if not path.exists():
            self.logger.error(f"File not found: {path}")
            return None

        try:
            stat = path.stat()
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries",
                "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,channels,bit_rate,tags,disposition",
                "-of", "json",
                str(path)
            ]

            p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await p.communicate()
            if p.returncode != 0:
                self.logger.error(f"ffprobe error: {err.decode().strip()}")
                return None

            probe = json.loads(out.decode() or "{}")
            fmt = probe.get("format", {})
            streams = probe.get("streams", [])

            media = MediaFileInfo(
                path=path,
                size=int(fmt.get("size", stat.st_size)),
                duration=float(fmt.get("duration", 0) or 0),
                media_type=MediaType.from_extension(path.suffix) or MediaType.MKV,
                bitrate=(int(fmt.get("bit_rate")) // 1000) if fmt.get("bit_rate") else 0
            )

            # Video -> width/height
            vs = [s for s in streams if s.get('codec_type') == 'video']
            if vs:
                v = vs[0]
                media.width = int(v.get("width", 0) or 0)
                media.height = int(v.get("height", 0) or 0)
                if not media.bitrate and v.get("bit_rate"):
                    media.bitrate = int(v.get("bit_rate")) // 1000

            # Audio streams
            for s in [s for s in streams if s.get('codec_type') == 'audio']:
                si = int(s.get('index', 0))
                codec_name = (s.get('codec_name') or "").lower()
                codec_enum = None
                try:
                    codec_enum = AudioCodec(codec_name)
                except Exception:
                    # fallback None
                    codec_enum = None
                tags = s.get('tags') or {}
                lang = tags.get('language', 'und')
                disp = s.get('disposition') or {}
                at = AudioTrack(stream_index=si, language=lang, codec=codec_enum,
                                channels=int(s.get('channels', 2) or 2),
                                is_default=bool(disp.get('default')))
                media.add_audio_track(at)

            # Attachment streams (e.g., attachments including .mka files)
            for s in [s for s in streams if s.get('codec_type') == 'attachment']:
                si = int(s.get('index', 0))
                tags = s.get('tags') or {}
                filename = tags.get('filename', '')
                mime = tags.get('mimetype', '')
                media.attachments.append({'index': si, 'filename': filename, 'mimetype': mime})

            # Subtitle streams (use global stream index!)
            for s in [s for s in streams if s.get('codec_type') == 'subtitle']:
                si = int(s.get('index', 0))
                codec_name = (s.get('codec_name') or "").lower()
                # determine codec & type
                if codec_name in ('hdmv_pgs_subtitle',):
                    codec = SubtitleCodec.PGS
                    s_type = 'graphic'
                elif codec_name in ('dvd_subtitle',):
                    codec = SubtitleCodec.VOBSUB
                    s_type = 'graphic'
                elif codec_name in ('ass',):
                    codec = SubtitleCodec.ASS
                    s_type = 'text'
                elif codec_name in ('ssa',):
                    codec = SubtitleCodec.SSA
                    s_type = 'text'
                elif codec_name in ('mov_text', 'tx3g', 'webvtt'):
                    codec = SubtitleCodec.MOV_TEXT
                    s_type = 'text'
                elif codec_name in ('srt', 'subrip'):
                    codec = SubtitleCodec.SRT
                    s_type = 'text'
                else:
                    # fallback
                    codec = SubtitleCodec.SRT
                    s_type = 'text'

                tags = s.get('tags') or {}
                lang = tags.get('language', 'und')
                disp = s.get('disposition') or {}
                sub = SubtitleTrack(stream_index=si, language=lang, codec=codec,
                                    is_default=bool(disp.get('default')), is_forced=bool(disp.get('forced')),
                                    stream_type=s_type)
                media.add_subtitle_track(sub)

            return media
        except Exception as e:
            self.logger.error(f"get_media_info failure: {e}", exc_info=True)
            return None

    async def _analyze_attachment(self, main_file: Path, attach_stream_index: int) -> Optional[MediaFileInfo]:
        """
        Extract an attachment stream (e.g., .mka) to a temp file and analyze it.
        attach_stream_index is the global ffprobe index of the attachment.
        """
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mka", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            # map by global stream index
            cmd = [
                self.ffmpeg_path,
                "-i", str(main_file),
                "-map", f"0:{attach_stream_index}",
                "-c", "copy",
                "-y", str(tmp_path)
            ]
            ok = await self._run_ffmpeg_command(cmd, timeout=120)
            if not ok:
                self.logger.error("Failed to extract attachment to temp file")
                return None

            info = await self.get_media_info(tmp_path)
            return info
        except Exception as e:
            self.logger.error(f"_analyze_attachment error: {e}", exc_info=True)
            return None
        finally:
            # remove temp file if exists
            try:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    async def extract_subtitles(self, input_path: Union[str, Path],
                                output_dir: Union[str, Path] = None) -> List[Path]:
        """
        Extract subtitles from a file. Handles:
         - subtitles directly in the file
         - attachments (e.g., .mka) attached in the file that contain subtitles
        Returns list of extracted file paths.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error("Input not found")
            return []

        outdir = Path(output_dir) if output_dir else self.output_path
        outdir.mkdir(parents=True, exist_ok=True)

        # gather media info
        media = await self.get_media_info(input_path)
        if not media:
            self.logger.error("Could not analyze input")
            return []

        extracted: List[Path] = []

        # If attachment .mka present, analyze it and import its subtitle streams (if any)
        for attach in media.attachments:
            filename = attach.get('filename', '') or ''
            if filename.lower().endswith('.mka') or filename.lower().endswith('.mkv'):
                self.logger.info(f"Found attachment {filename} at stream {attach.get('index')}; analyzing...")
                nested = await self._analyze_attachment(input_path, attach.get('index'))
                if nested and nested.subtitle_tracks:
                    # we need to mark these tracks as coming from that attachment (so we can extract later)
                    for sub in nested.subtitle_tracks:
                        # mark container_attachment_index with attachment stream index
                        sub.container_attachment_index = attach.get('index')
                        # adjust path (we'll extract from the temp mka, not directly from original)
                        media.add_subtitle_track(sub)

        # If still no subtitle stream, check audio tracks maybe referencing embedded container (less common)
        if not media.subtitle_tracks:
            self.logger.info("No subtitle streams found in top-level stream list")

        # Prepare extraction tasks: use stream_index for mapping (-map 0:STREAM_INDEX)
        tasks = []
        for sub in media.subtitle_tracks:
            try:
                # If sub came from an attachment, we will later extract the attachment to tmp and call extract_subtitles on it.
                if sub.container_attachment_index is not None:
                    # postpone extraction via extract_subtitles_from_attachment
                    continue

                stream_idx = sub.stream_index
                base = input_path.stem
                if sub.stream_type == 'text':
                    out_ext = "srt"
                    out_path = outdir / f"{base}_{sub.language}_{stream_idx}.{out_ext}"
                    cmd = [
                        self.ffmpeg_path,
                        "-i", str(input_path),
                        "-map", f"0:{stream_idx}",
                        "-c:s", "srt",  # transcode text-like subs to srt when possible
                        "-y", str(out_path)
                    ]
                else:
                    # graphic subtitle, cannot transcode to srt automatically: copy to .sup/.sub
                    out_ext = sub.codec.extension
                    out_path = outdir / f"{base}_{sub.language}_{stream_idx}.{out_ext}"
                    cmd = [
                        self.ffmpeg_path,
                        "-i", str(input_path),
                        "-map", f"0:{stream_idx}",
                        "-c:s", "copy",
                        "-y", str(out_path)
                    ]
                tasks.append((cmd, out_path))
            except Exception as e:
                self.logger.error(f"Preparing extraction for stream {sub.stream_index} failed: {e}")

        # Execute extraction tasks sequentially (safe). Could be parallelized with limits if desired.
        for cmd, out_path in tasks:
            ok = await self._run_ffmpeg_command(cmd, timeout=120)
            if ok and out_path.exists():
                extracted.append(out_path)
                self.logger.info(f"Extracted subtitle to {out_path}")
            else:
                # Even if ffmpeg exits 0, sometimes output file is not created; check and log
                if out_path.exists():
                    extracted.append(out_path)
                    self.logger.info(f"Extracted subtitle to {out_path}")
                else:
                    self.logger.warning(f"Failed to extract subtitle to {out_path}")

        # Now handle subtitle tracks that came from attachments: extract the attachment to temp and re-run extraction
        for sub in [s for s in media.subtitle_tracks if s.container_attachment_index is not None]:
            att_idx = sub.container_attachment_index
            if att_idx is None:
                continue
            self.logger.info(f"Extracting attachment (index {att_idx}) to obtain subtitle stream {sub.stream_index}")
            # create temp mka and extract attachment
            tmp_mka = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".mka", delete=False) as tmpf:
                    tmp_mka = Path(tmpf.name)

                # Extract attachment to tmp_mka by global stream index att_idx
                cmd_extract_att = [
                    self.ffmpeg_path,
                    "-i", str(input_path),
                    "-map", f"0:{att_idx}",
                    "-c", "copy",
                    "-y", str(tmp_mka)
                ]
                if not await self._run_ffmpeg_command(cmd_extract_att, timeout=120):
                    self.logger.error(f"Failed to extract attachment stream {att_idx}")
                    continue

                # Now call extract_subtitles on tmp_mka (recursive, but tmp_mka should contain straightforward subs)
                found = await self.extract_subtitles(tmp_mka, outdir)
                extracted.extend(found)
            finally:
                try:
                    if tmp_mka and tmp_mka.exists():
                        tmp_mka.unlink()
                except Exception:
                    pass

        return extracted

    async def convert_audio(self, input_path: Union[str, Path],
                        output_name: str,
                        codec: AudioCodec = AudioCodec.AAC,
                        bitrate: int = 192) -> Optional[Path]:
        """
        Convert audio with optimized parameters and resource usage.
        
        Args:
            input_path: Path to input file
            output_name: Name for output file (without extension)
            codec: Target audio codec (default: AAC)
            bitrate: Target bitrate in kbps (default: 192)
            
        Returns:
            Path to converted file or None if failed
        """
        input_path = Path(input_path)
        output_path = self.output_path / f"{output_name}.{codec.extension}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-vn",
            "-c:a", codec.name.lower(),
            "-b:a", f"{bitrate}k",
        ]
        
        if codec == AudioCodec.AAC:
            command.extend(["-aac_coder", "twoloop"]) 
        elif codec == AudioCodec.OPUS:
            command.extend(["-application", "audio"])  
        
        command.extend([
            "-threads", str(min(2, self.thread_count)),  
            "-y",
            str(output_path)
        ])
        
        self.logger.info(f"Converting {input_path.name} to {codec} at {bitrate}kbps")
        if await self._run_ffmpeg_command(command, timeout=300):
            return output_path
        return None

    async def generate_thumbnail(self, input_path: Union[str, Path],
                            output_name: str,
                            time_offset: str = "00:00:05",
                            width: int = 640) -> Optional[Path]:
        """
        Generate optimized thumbnail with smart scaling and faster capture.
        
        Args:
            input_path: Path to input video
            output_name: Name for output image (without extension)
            time_offset: Time position to capture (HH:MM:SS)
            width: Width of thumbnail (height auto-calculated)
            
        Returns:
            Path to generated thumbnail or None if failed
        """
        input_path = Path(input_path)
        output_path = self.output_path / f"{output_name}.jpg"
        
        command = [
            self.ffmpeg_path,
            "-ss", time_offset,  
            "-i", str(input_path),
            "-frames:v", "1",
            "-vf", f"scale={width}:-2:flags=lanczos", 
            "-q:v", "3",  
            "-f", "image2",
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Generating thumbnail for {input_path.name}")
        if await self._run_ffmpeg_command(command, timeout=60): 
            return output_path
        return None

    async def add_subtitle(self, sbt_file: Union[str, Path],  
                        input_path: Union[str, Path],
                        output_name: str, 
                        language: str = "eng", 
                        index: int = 0,
                        is_default: bool = True,
                        is_forced: bool = False) -> Optional[Path]:
        """
        Optimized subtitle addition with smart format detection and parallel processing.
        """
        sbt_path = Path(sbt_file)
        input_path = Path(input_path)
        output_path = self.output_path / f"{output_name}{input_path.suffix}"
        

        if not sbt_path.exists() or not input_path.exists():
            self.logger.error(f"Missing files: {'subtitle' if not sbt_path.exists() else 'video'} not found")
            return None

        input_ext = input_path.suffix.lower()
        sbt_ext = sbt_path.suffix.lower()[1:]
        
        disposition = []
        if is_default:
            disposition.append("default")
        if is_forced:
            disposition.append("forced")
        disposition_str = "+".join(disposition) if disposition else "0"

        softsub_supported = input_ext in ('.mkv', '.webm') or (input_ext == '.mp4' and sbt_ext in ('srt', 'vtt'))
        
        if softsub_supported:
            sub_codec = {
                'ass': 'ass',
                'ssa': 'ass',
                'srt': 'mov_text' if input_ext == '.mp4' else 'srt',
                'vtt': 'mov_text' if input_ext == '.mp4' else 'webvtt'
            }.get(sbt_ext, 'mov_text' if input_ext == '.mp4' else 'srt')

            command = [
                self.ffmpeg_path,
                "-i", str(input_path),
                "-i", str(sbt_path),
                "-map", "0",
                "-map", "1:0",
                "-c:v", "copy",
                "-c:a", "copy",
                "-c:s", sub_codec,
                f"-metadata:s:s:{index}", f"language={language}",
                f"-disposition:s:{index}", disposition_str,
                "-threads", str(min(4, self.thread_count)),  # Limit threads
                "-y",
                str(output_path)
            ]

            self.logger.info(f"Attempting optimized softsub for {input_path.name}")
            if await self._run_ffmpeg_command(command, timeout=600):
                return output_path

        try:
            temp_sbt = None
            if sbt_ext == "vtt":
                temp_sbt = sbt_path.with_suffix(".srt")
                if not await self._convert_vtt_to_srt(sbt_path, temp_sbt):
                    self.logger.error("VTT conversion failed")
                    return None
                sbt_path = temp_sbt

            sub_path = str(sbt_path).replace(':', '\\:') if sys.platform == 'win32' else f"'{str(sbt_path)}'"

            command = [
                self.ffmpeg_path,
                "-i", str(input_path),
                "-vf", f"subtitles={sub_path}:force_style='Fontsize=24,Outline=1'",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-threads", str(min(4, self.thread_count)), 
                "-y",
                str(output_path)
            ]

            self.logger.info(f"Running optimized hardsub for {input_path.name}")
            if await self._run_ffmpeg_command(command, timeout=900):
                return output_path

        except Exception as e:
            self.logger.error(f"Subtitle processing failed: {str(e)}")
        finally:
            if temp_sbt and temp_sbt.exists():
                try:
                    temp_sbt.unlink()
                except:
                    pass

        return None

    async def _convert_vtt_to_srt(self, vtt_path: Path, srt_path: Path) -> bool:
        """Convert VTT subtitles to SRT format"""
        try:
            command = [
                self.ffmpeg_path,
                "-i", str(vtt_path),
                "-f", "srt",
                "-y",
                str(srt_path)
            ]
            return await self._run_ffmpeg_command(command)
        except Exception as e:
            self.logger.error(f"VTT to SRT conversion failed: {str(e)}")
            return False
    
    async def convert_container(self, input_path: Path, output_name: str, output_format: MediaType) -> Optional[Path]:
        """Convertit un fichier multimédia dans un autre conteneur sans ré-encoder"""
        output_path = self.output_path / f"{output_name}{output_format.value}"
        
        cmd = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-c", "copy", 
            "-y",  
            str(output_path)
        ]
        
        if await self._run_ffmpeg_command(cmd):
            return output_path
        return None


    async def remove_subtitles(self, input_path: Union[str, Path],
                            output_name: str) -> Optional[Path]:
        """
        Optimized subtitle removal with stream copy and minimal processing.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            
        Returns:
            Path to output file without subtitles, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None
            
        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-map", "0",
            "-map", "-0:s",  
            "-map", "-0:t",
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart" if output_ext.lower() == ".mp4" else "",
            "-threads", "2",  
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Removing subtitles from {input_path.name}")
        if await self._run_ffmpeg_command(command, timeout=300):
            return output_path
        return None

    async def extract_audio(self, input_path: Union[str, Path],
                        output_name: str,
                        codec: AudioCodec = AudioCodec.AAC,
                        bitrate: int = 192) -> Optional[Path]:
        """
        Optimized audio extraction with codec-specific optimizations.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            codec: Audio codec to use (default: AAC)
            bitrate: Audio bitrate in kbps (default: 192)
            
        Returns:
            Path to extracted audio file, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None
            
        output_path = self.output_path / f"{output_name}.{codec.extension}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-vn",  
            "-c:a", codec.name.lower(),
            "-b:a", f"{bitrate}k",
        ]
        
        if codec == AudioCodec.AAC:
            command.extend(["-aac_coder", "twoloop"]) 
        elif codec == AudioCodec.OPUS:
            command.extend(["-application", "audio"])
        
        command.extend([
            "-threads", "2",
            "-y",
            str(output_path)
        ])
        
        self.logger.info(f"Extracting audio to {codec} at {bitrate}kbps")
        if await self._run_ffmpeg_command(command, timeout=300):
            return output_path
        return None

    async def merge_video_audio(self, video_path: Union[str, Path],
                            audio_path: Union[str, Path],
                            output_name: str) -> Optional[Path]:
        """
        Optimized video-audio merging with smart stream handling.
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file to merge
            output_name: Name for output file (without extension)
            
        Returns:
            Path to merged file, or None if failed
        """
        video_path = Path(video_path)
        audio_path = Path(audio_path)
        
        if not video_path.exists() or not audio_path.exists():
            missing = "video" if not video_path.exists() else "audio"
            self.logger.error(f"{missing.capitalize()} file not found")
            return None
            
        output_ext = video_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0",  
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart" if output_ext.lower() == ".mp4" else "",
            "-shortest",  
            "-threads", str(min(4, self.thread_count)),  
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Merging {video_path.name} with {audio_path.name}")
        try:
            if await self._run_ffmpeg_command(command, timeout=600):
                if output_path.exists() and output_path.stat().st_size > 1024:
                    return output_path
                self.logger.error("Output file invalid (too small or missing)")
        except Exception as e:
            self.logger.error(f"Merge failed: {str(e)}", exc_info=True)
        
        return None
    
    async def remove_audio(self, input_path: Union[str, Path],
                        output_name: str) -> Optional[Path]:
        """
        Optimized audio removal with stream copy and minimal processing.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            
        Returns:
            Path to output file without audio, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None
            
        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-map", "0:v", 
            "-map", "-0:a",
            "-c:v", "copy",  
            "-movflags", "+faststart" if output_ext.lower() == ".mp4" else "",
            "-threads", "2",  
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Removing audio from {input_path.name}")
        if await self._run_ffmpeg_command(command, timeout=300):
            return output_path
        return None

    async def choose_subtitle(self, input_path: Union[str, Path],
                        output_name: str,
                        language: Optional[str] = None,
                        index: Optional[int] = None,
                        make_default: bool = False) -> Optional[Path]:
        """
        Optimized subtitle selection with minimal stream processing.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            language: Language code to select (ISO 639)
            index: Specific subtitle track index to select
            make_default: Whether to make selected subtitle default
            
        Returns:
            Path to output file with selected subtitles, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None
        if language is None and index is None:
            self.logger.error("Must specify language or index")
            return None
            
        media_info = await self.get_media_info(input_path)
        if not media_info or not media_info.subtitle_tracks:
            self.logger.info(f"No subtitles in {input_path.name}")
            return None
            
        selected_sub = next(
            (s for s in media_info.subtitle_tracks 
            if (index is not None and s.index == index) or 
                (language is not None and s.language.lower() == language.lower())),
            None
        )
        
        if not selected_sub:
            self.logger.error(f"No matching subtitle (lang={language}, idx={index})")
            return None
            
        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-map", "0",  
            "-map", f"0:s:{selected_sub.index-1}", 
            "-c", "copy",  
            "-disposition:s:0", "default" if make_default else "0",
            "-movflags", "+faststart" if output_ext.lower() == ".mp4" else "",
            "-threads", "2",  
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Selecting subtitle {selected_sub.index} from {input_path.name}")
        if await self._run_ffmpeg_command(command, timeout=300):
            return output_path
        return None

    async def choose_subtitle_burn(self, input_path: Union[str, Path],
                                output_name: str,
                                language: Optional[str] = None,
                                index: Optional[int] = None) -> Optional[Path]:
        """
        Optimized subtitle burning with smart encoding settings.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            language: Language code to select (ISO 639)
            index: Specific subtitle track index to select
                    
        Returns:
            Path to output file with burned subtitles, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None
        if language is None and index is None:
            self.logger.error("Must specify language or index")
            return None
            
        media_info = await self.get_media_info(input_path)
        if not media_info or not media_info.subtitle_tracks:
            self.logger.info(f"No subtitles in {input_path.name}")
            return None
            
        selected_sub = next(
            (s for s in media_info.subtitle_tracks 
            if (index is not None and s.index == index) or 
                (language is not None and s.language.lower() == language.lower())),
            None
        )
        
        if not selected_sub:
            self.logger.error(f"No matching subtitle (lang={language}, idx={index})")
            return None
            
        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"
        
        safe_path = str(input_path).replace(':', '\\:') if sys.platform == 'win32' else f"'{str(input_path)}'"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-vf", f"subtitles={safe_path}:si={selected_sub.index-1}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-threads", str(min(4, self.thread_count)), 
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Burning subtitle {selected_sub.index} into {input_path.name}")
        if await self._run_ffmpeg_command(command, timeout=900):
            return output_path
        return None

    async def choose_audio(self, input_path: Union[str, Path],
                        output_name: str,
                        language: Optional[str] = None,
                        index: Optional[int] = None,
                        make_default: bool = False) -> Optional[Path]:
        """
        Optimized audio track selection with minimal stream processing.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            language: Language code to select (ISO 639)
            index: Specific audio track index to select
            make_default: Whether to make selected audio default
            
        Returns:
            Path to output file with selected audio, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None
        if language is None and index is None:
            self.logger.error("Must specify language or index")
            return None
            
        media_info = await self.get_media_info(input_path)
        if not media_info or not media_info.audio_tracks:
            self.logger.info(f"No audio tracks in {input_path.name}")
            return None
            
        selected_audio = next(
            (a for a in media_info.audio_tracks 
            if (index is not None and a.index == index) or 
                (language is not None and a.language.lower() == language.lower())),
            None
        )
        
        if not selected_audio:
            self.logger.error(f"No matching audio (lang={language}, idx={index})")
            return None
            
        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"
        
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-map", "0:v", 
            "-map", f"0:a:{selected_audio.index-1}",  
            "-c", "copy", 
            "-disposition:a:0", "default" if make_default else "0",
            "-movflags", "+faststart" if output_ext.lower() == ".mp4" else "",
            "-threads", "2",  
            "-y",
            str(output_path)
        ]
        
        self.logger.info(f"Selecting audio {selected_audio.index} from {input_path.name}")
        if await self._run_ffmpeg_command(command, timeout=300):
            return output_path
        return None

    async def get_chapters(self, input_path: Union[str, Path]) -> Optional[List[Dict[str, Any]]]:
        """
        Optimized chapter extraction with efficient parsing.
        
        Args:
            input_path: Path to input media file
            
        Returns:
            List of chapter dicts with 'start', 'end', 'title',
            or None if no chapters or error
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None

        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-f", "ffmetadata",
            "-",
            "-loglevel", "error"
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=512 * 1024 
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            
            if process.returncode != 0:
                error_msg = stderr.decode(errors='ignore').strip()
                self.logger.error(f"Chapter extraction failed: {error_msg[:200]}...")
                return None

            metadata = stdout.decode()
            if not metadata:
                self.logger.debug(f"No chapters in {input_path.name}")
                return None

            chapters = []
            current = {}
            for line in metadata.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line == '[CHAPTER]':
                    if current:
                        chapters.append(current)
                    current = {}
                elif line.startswith('START='):
                    current['start'] = self._convert_timestamp(line[6:])
                elif line.startswith('END='):
                    current['end'] = self._convert_timestamp(line[4:])
                elif line.startswith('title='):
                    current['title'] = line[6:]

            if current:
                chapters.append(current)

            return chapters if chapters else None
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Chapter extraction timeout for {input_path.name}")
            try:
                process.kill()
                await process.wait()
            except:
                pass
            return None
        except Exception as e:
            self.logger.error(f"Chapter error: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _convert_timestamp(timestamp: str) -> str:
        """Optimized timestamp conversion to HH:MM:SS format."""
        if not timestamp:
            return "00:00:00"
        
        if re.fullmatch(r'\d{2}:\d{2}:\d{2}(\.\d+)?', timestamp):
            return timestamp.split('.')[0]
        
        try:
            secs = float(timestamp)
            return f"{int(secs//3600):02d}:{int(secs%3600//60):02d}:{int(secs%60):02d}"
        except:
            return timestamp
        
    async def get_chapter(self, input_path: Union[str, Path], chapter_index: int) -> Optional[Dict[str, Any]]:
        """
        Optimized chapter retrieval with early validation.
        
        Args:
            input_path: Path to input media file
            chapter_index: 1-based index of chapter to retrieve
            
        Returns:
            Chapter dict or None if not found
        """
        if chapter_index < 1:
            self.logger.debug(f"Invalid chapter index: {chapter_index}")
            return None
            
        chapters = await self.get_chapters(input_path)
        return chapters[chapter_index - 1] if chapters and chapter_index <= len(chapters) else None

    @staticmethod
    def hms_to_seconds(hms: str) -> float:
        """Optimized conversion from HH:MM:SS to seconds."""
        try:
            parts = list(map(float, hms.split(':')))
            if len(parts) == 3:  # HH:MM:SS
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:  # MM:SS
                return parts[0] * 60 + parts[1]
            return float(hms)  # SS
        except (ValueError, AttributeError):
            return 0.0

    async def add_chapters(self, input_path: Union[str, Path],
                        output_name: str,
                        chapters: List[Dict[str, Any]]) -> Optional[Path]:
        """
        Optimized chapter addition with efficient metadata handling.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        metadata_content = [";FFMETADATA1\n"]
        for i, chapter in enumerate(chapters, 1):
            try:
                start_ms = int(self.hms_to_seconds(chapter['start']) * 1000)
                end_ms = int(self.hms_to_seconds(chapter['end']) * 1000)
                title = chapter.get('title', f'Chapter {i}')
                metadata_content.append(
                    f"[CHAPTER]\nTIMEBASE=1/1000\n"
                    f"START={start_ms}\nEND={end_ms}\n"
                    f"title={title}\n\n"
                )
            except KeyError as e:
                self.logger.error(f"Missing chapter field: {str(e)}")
                return None

        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=str(self.output_path), delete=False) as f:
                f.writelines(metadata_content)
                metadata_path = Path(f.name)
        except Exception as e:
            self.logger.error(f"Failed to create chapter file: {str(e)}")
            return None

        output_path = self.output_path / f"{output_name}{input_path.suffix}"
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-i", str(metadata_path),
            "-map_metadata", "1",
            "-c", "copy",
            "-threads", "2", 
            "-y",
            str(output_path)
        ]

        try:
            success = await self._run_ffmpeg_command(command, timeout=300)
            return output_path if success else None
        finally:
            try:
                metadata_path.unlink()
            except:
                pass

    async def remove_chapters(self, input_path: Union[str, Path],
                            output_name: str) -> Optional[Path]:
        """
        Efficient chapter removal with stream copy optimization.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        output_path = self.output_path / f"{output_name}{input_path.suffix}"
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-map_metadata", "-1",
            "-c", "copy",
            "-threads", "2", 
            "-movflags", "+faststart" if output_path.suffix.lower() == '.mp4' else "",
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Removing chapters from {input_path.name}")
        return output_path if await self._run_ffmpeg_command(command, timeout=180) else None

    async def edit_chapter(self, input_path: Union[str, Path],
                        output_name: str,
                        chapter_index: int,
                        new_start: Optional[str] = None,
                        new_end: Optional[str] = None,
                        new_title: Optional[str] = None) -> Optional[Path]:
        """
        Optimized chapter editing with minimal copying.
        """
        if chapter_index < 1:
            self.logger.debug(f"Invalid chapter index: {chapter_index}")
            return None

        chapters = await self.get_chapters(input_path)
        if not chapters or chapter_index > len(chapters):
            self.logger.error(f"Chapter {chapter_index} not found")
            return None

        modified_chapters = []
        for i, chapter in enumerate(chapters, 1):
            if i == chapter_index:
                new_chapter = dict(chapter)
                if new_start is not None:
                    new_chapter['start'] = new_start
                if new_end is not None:
                    new_chapter['end'] = new_end
                if new_title is not None:
                    new_chapter['title'] = new_title
                modified_chapters.append(new_chapter)
            else:
                modified_chapters.append(dict(chapter))

        return await self.add_chapters(input_path, output_name, modified_chapters)
    
    async def split_chapter(self, input_path: Union[str, Path],
                        output_name: str,
                        chapter_index: int,
                        split_time: float) -> Optional[Path]:
        """
        Optimized chapter splitting with minimal data copying.
        
        Args:
            input_path: Path to input media file
            output_name: Base name for output file
            chapter_index: 1-based chapter index to split
            split_time: Split point in seconds
            
        Returns:
            Path to output file or None if failed
        """
        if chapter_index < 1:
            self.logger.debug(f"Invalid chapter index: {chapter_index}")
            return None

        chapters = await self.get_chapters(input_path)
        if not chapters or chapter_index > len(chapters):
            self.logger.error(f"Chapter {chapter_index} not found")
            return None

        chapter = chapters[chapter_index - 1]
        try:
            start = float(chapter['start'])
            end = float(chapter['end'])
            if not (start < split_time < end):
                self.logger.error("Split time must be within chapter")
                return None
        except (ValueError, KeyError) as e:
            self.logger.error(f"Invalid chapter times: {str(e)}")
            return None

        new_chapters = [
            *chapters[:chapter_index - 1],
            {'start': start, 'end': split_time, 'title': f"{chapter.get('title', 'Chapter')} Part 1"},
            {'start': split_time, 'end': end, 'title': f"{chapter.get('title', 'Chapter')} Part 2"},
            *chapters[chapter_index:]
        ]

        return await self.add_chapters(input_path, output_name, new_chapters)

    async def trim_video(self, input_path: Union[str, Path],
                    output_name: str,
                    start_time: float,
                    end_time: float) -> Optional[Path]:
        """
        Optimized video trimming with keyframe accuracy.
        
        Args:
            input_path: Path to input video
            output_name: Base name for output file
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            Path to trimmed file or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None

        output_path = self.output_path / f"{output_name}{input_path.suffix}"
        
        command = [
            self.ffmpeg_path,
            "-ss", str(max(0, start_time - 1)),  
            "-i", str(input_path),
            "-ss", str(max(0, 1 - (start_time - int(start_time)))), 
            "-to", str(end_time - start_time),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-threads", "2",  
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Trimming {input_path.name} ({start_time}s-{end_time}s)")
        return output_path if await self._run_ffmpeg_command(command, timeout=600) else None

    async def cut_video(self, input_path: Union[str, Path],
                    output_name: str,
                    cut_ranges: List[Tuple[float, float]]) -> Optional[Path]:
        """
        Optimized video cutting with efficient filter graph.
        
        Args:
            input_path: Path to input video
            output_name: Base name for output file
            cut_ranges: List of (start,end) ranges to cut
            
        Returns:
            Path to cut file or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input not found: {input_path}")
            return None

        if not cut_ranges:
            self.logger.info("No cut ranges specified")
            return input_path

        cut_ranges = sorted((min(s,e), max(s,e)) for s,e in cut_ranges)
        merged = []
        for current in cut_ranges:
            if merged and current[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], current[1]))
            else:
                merged.append(current)

        media_info = await self.get_media_info(input_path)
        duration = media_info.duration if media_info else float('inf')

        filter_parts = []
        concat_inputs = []
        last_end = 0.0
        
        for i, (start, end) in enumerate(merged):
            if last_end < start:
                filter_parts.append(
                    f"[0:v]trim=start={last_end}:end={start},setpts=N/FRAME_RATE/TB[v{i}];"
                    f"[0:a]atrim=start={last_end}:end={start},asetpts=N/SR/TB[a{i}];"
                )
                concat_inputs.extend([f"[v{i}]", f"[a{i}]"])
            last_end = end

        if last_end < duration:
            filter_parts.append(
                f"[0:v]trim=start={last_end},setpts=N/FRAME_RATE/TB[v{len(merged)}];"
                f"[0:a]atrim=start={last_end},asetpts=N/SR/TB[a{len(merged)}];"
            )
            concat_inputs.extend([f"[v{len(merged)}]", f"[a{len(merged)}]"])

        filter_complex = (
            "".join(filter_parts) +
            f"{''.join(concat_inputs)}concat=n={len(concat_inputs)//2}:v=1:a=1[vout][aout]"
        )

        output_path = self.output_path / f"{output_name}{input_path.suffix}"
        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-threads", str(min(4, self.thread_count)),
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Cutting {len(merged)} ranges from {input_path.name}")
        return output_path if await self._run_ffmpeg_command(command, timeout=1800) else None

    
    async def concat_video(self, input_paths: List[Union[str, Path]],
                        output_name: str,
                        output_format: MediaType = MediaType.MP4,
                        transition_duration: float = 0.0) -> Optional[Path]:
        """
        Optimized video concatenation with efficient transition handling.
        
        Args:
            input_paths: List of input video paths
            output_name: Output filename (without extension)
            output_format: Output media format
            transition_duration: Crossfade duration (0 for no transition)
            
        Returns:
            Path to concatenated file or None if failed
        """
        if not input_paths:
            self.logger.error("No input files provided")
            return None

        input_files = []
        for path in input_paths:
            file = Path(path)
            if not file.exists():
                self.logger.error(f"Input file not found: {file}")
                return None
            input_files.append(file)

        output_path = self.output_path / f"{output_name}.{output_format.value}"

        if transition_duration <= 0:
            return await self._simple_concat(input_files, output_path)
        
        return await self._transition_concat(input_files, output_path, transition_duration)

    async def _simple_concat(self, input_files: List[Path], output_path: Path) -> Optional[Path]:
        """Optimized simple concatenation without transitions."""
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=str(self.output_path), delete=False) as f:
                for file in input_files:
                    f.write(f"file '{file.absolute()}'\n")
                list_file = Path(f.name)
        except Exception as e:
            self.logger.error(f"Failed to create concat list: {str(e)}")
            return None

        command = [
            self.ffmpeg_path,
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-movflags", "+faststart",
            "-threads", "2",
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Concatenating {len(input_files)} videos (stream copy)")
        success = await self._run_ffmpeg_command(command, timeout=600)
        
        if not success:
            self.logger.info("Stream copy failed, attempting re-encode")
            command[7:7] = ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "192k"]
            success = await self._run_ffmpeg_command(command, timeout=1800)

        try:
            list_file.unlink()
        except:
            pass

        return output_path if success else None

    async def _transition_concat(self, input_files: List[Path], 
                            output_path: Path,
                            transition_duration: float) -> Optional[Path]:
        """Concatenation with perfect audio-video sync and smooth transitions."""
        try:
            media_infos = await asyncio.gather(*[self.get_media_info(f) for f in input_files])
            if None in media_infos:
                self.logger.error("Missing media info for some files")
                return None

            target_width = media_infos[0].width
            target_height = media_infos[0].height

            filter_complex = []
            inputs = []
            
            for i, (file, mi) in enumerate(zip(input_files, media_infos)):
                inputs.extend(["-i", str(file)])
                
                filter_complex.append(
                    f"[{i}:v]scale={target_width}:{target_height}:"
                    f"force_original_aspect_ratio=decrease,"
                    f"pad={target_width}:{target_height}:-1:-1:color=black[v{i}];"
                )
                
                filter_complex.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}];")

            for i in range(len(input_files) - 1):
                if i == 0:
                    base = f"[v{i}]"
                else:
                    base = f"[vout{i-1}]"
                    
                next_vid = f"[v{i+1}]"
                transition_start = max(0, media_infos[i].duration - transition_duration)
                
                filter_complex.append(
                    f"{base}{next_vid}xfade=transition=fade:duration={transition_duration}:"
                    f"offset={transition_start}[vout{i}];"
                )

            for i in range(len(input_files) - 1):
                if i == 0:
                    audio_base = f"[a{i}]"
                else:
                    audio_base = f"[across{i-1}]"
                    
                next_aud = f"[a{i+1}]"
                afade_duration = transition_duration * 1000 
                afade_start = max(0, media_infos[i].duration - transition_duration)
                
                filter_complex.append(
                    f"{audio_base}atrim=0:{afade_start}[atrim{i}];"
                    f"{audio_base}atrim={afade_start},asetpts=PTS-STARTPTS[afadeout{i}];"
                    f"{next_aud}atrim=0:{transition_duration},asetpts=PTS-STARTPTS[afadein{i+1}];"
                    f"[afadeout{i}][afadein{i+1}]acrossfade=d={afade_duration}[across{i}];"
                    f"[atrim{i}][across{i}]concat=n=2:v=0:a=1[amix{i}];"
                )

            final_video = f"[vout{len(input_files)-2}]" if len(input_files) > 1 else "[v0]"
            
            if len(input_files) > 1:
                final_audio = f"[amix{len(input_files)-2}]"
            else:
                final_audio = "[a0]"

            command = [
                self.ffmpeg_path,
                *inputs,
                "-filter_complex", "".join(filter_complex),
                "-map", final_video,
                "-map", final_audio,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-y",
                str(output_path)
            ]

            self.logger.debug("Full FFmpeg command: " + " ".join(command))
            return output_path if await self._run_ffmpeg_command(command, timeout=3600) else None

        except Exception as e:
            self.logger.error(f"Advanced transition failed: {str(e)}", exc_info=True)
            return None
    
    RESOLUTION_PROFILES = {
        '144p': {
            'scale': 144,
            'video_bitrate': (150, 300),
            'audio_bitrate': '64k',
            'min_size_mb': 5,
            'crf': 32,
            'max_threads': 2
        },
        '240p': {
            'scale': 240,
            'video_bitrate': (300, 600),
            'audio_bitrate': '64k',
            'min_size_mb': 10,
            'crf': 28,
            'max_threads': 2
        },
        '360p': {
            'scale': 360,
            'video_bitrate': (600, 1000),
            'audio_bitrate': '96k',
            'min_size_mb': 20,
            'crf': 26,
            'max_threads': 4
        },
        '480p': {
            'scale': 480,
            'video_bitrate': (1000, 1500),
            'audio_bitrate': '96k',
            'min_size_mb': 30,
            'crf': 24,
            'max_threads': 4
        },
        '720p': {
            'scale': 720,
            'video_bitrate': (1500, 3000),
            'audio_bitrate': '128k',
            'min_size_mb': 50,
            'crf': 22,
            'max_threads': 6,
            'two_pass': True  
        },
        '1080p': {
            'scale': 1080,
            'video_bitrate': (3000, 6000),
            'audio_bitrate': '128k',
            'min_size_mb': 80,
            'crf': 20,
            'max_threads': 8,
            'two_pass': True
        }
    }

    FORMAT_PROFILES = {
        'mp4': {
            'video_codec': 'libx264',
            'audio_codec': 'aac',
            'extension': 'mp4',
            'preset': 'fast',  
            'tune': 'fastdecode',  
            'profile': 'main',
            'level': '4.0',
            'container_options': ['-movflags', '+faststart']
        },
        'hevc': {
            'video_codec': 'libx265',
            'audio_codec': 'aac',
            'extension': 'mp4',
            'preset': 'fast',  
            'tune': 'fastdecode',
            'profile': 'main',
            'container_options': ['-tag:v', 'hvc1'],
            'max_threads': 4  
        },
        'webm': {
            'video_codec': 'libvpx-vp9',
            'audio_codec': 'libopus',
            'extension': 'webm',
            'speed': 4,  
            'quality': 'good',
            'row-mt': 1,
            'max_threads': 8  
        }
    }
    
    async def compress_video(self, input_path: Union[str, Path],
                        output_basename: str,
                        target_formats: List[str] = ['mp4', 'hevc'],
                        keep_original_quality: bool = False,
                        two_pass: bool = False) -> Dict[str, List[Path]]:
        """
        Robust video compression with complete error handling.
        
        Args:
            input_path: Path to input video file
            output_basename: Base name for output files
            target_formats: Formats to generate
            keep_original_quality: Keep original resolution versions
            two_pass: Use two-pass encoding
            
        Returns:
            Dictionary of generated files by format
        """
        try:
            input_path = Path(input_path)
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")

            # Ensure output directory exists
            self.output_path.mkdir(parents=True, exist_ok=True)

            # Get detailed media info with fallback
            media_info = await self.get_media_info(input_path)
            if not media_info:
                raise ValueError("Could not get media info")

            # Fallback for height detection
            if media_info.height <= 0:
                self.logger.warning("Using fallback height detection")
                media_info.height = await self._detect_fallback_height(input_path)
                if media_info.height <= 0:
                    raise ValueError("Could not determine video height")

            # Prepare resolutions
            resolutions = self._get_valid_resolutions(media_info.height, keep_original_quality)
            if not resolutions:
                raise ValueError("No valid resolutions found")

            # Process formats
            results = await self._process_all_formats(
                input_path, output_basename,
                target_formats, resolutions, two_pass
            )

            return results

        except Exception as e:
            self.logger.error(f"Compression failed: {str(e)}", exc_info=True)
            return {}

    async def _detect_fallback_height(self, input_path: Path) -> int:
        """Fallback method to detect video height."""
        command = [
            self.ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=height",
            "-of", "csv=p=0",
            str(input_path)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            return int(stdout.decode().strip())
        except:
            return 0

    def _get_valid_resolutions(self, original_height: int, keep_original: bool) -> List[Tuple[str, dict]]:
        """Get filtered and sorted resolutions."""
        resolutions = [
            (name, profile) for name, profile in self.RESOLUTION_PROFILES.items()
            if profile['scale'] <= original_height or 
            (keep_original and profile['scale'] == original_height)
        ]
        return sorted(resolutions, key=lambda x: x[1]['scale'])

    async def _process_all_formats(self, input_path: Path, output_basename: str,
                                target_formats: List[str], resolutions: List[Tuple[str, dict]],
                                two_pass: bool) -> Dict[str, List[Path]]:
        """Process all formats in parallel."""
        results = defaultdict(list)
        tasks = []
        
        format_profiles = {
            k: v for k, v in self.FORMAT_PROFILES.items()
            if k in target_formats
        }

        for fmt, fmt_profile in format_profiles.items():
            for res_name, res_profile in resolutions:
                task = self._process_compression(
                    input_path, output_basename,
                    fmt, fmt_profile, res_name, res_profile,
                    two_pass, results
                )
                tasks.append(task)

        await asyncio.gather(*tasks)
        return dict(results)

    async def _process_compression(self, input_path: Path, output_basename: str,
                                fmt: str, fmt_profile: dict,
                                res_name: str, res_profile: dict,
                                two_pass: bool, results: defaultdict):
        """
        Process a single compression task with optimized settings.
        """
        output_name = f"{output_basename}_{res_name}"
        output_path = self.output_path / f"{output_name}.{fmt_profile['extension']}"
        
        if output_path.exists() and output_path.stat().st_size > 0:
            results[fmt].append(output_path)
            return

        avg_bitrate = sum(res_profile['video_bitrate']) // 2
        max_bitrate = res_profile['video_bitrate'][1]
        min_bitrate = res_profile['video_bitrate'][0]

        command = [
            self.ffmpeg_path,
            "-hwaccel", "auto",  
            "-i", str(input_path),
            "-vf", f"scale=-2:{res_profile['scale']}",
            "-c:v", fmt_profile['video_codec'],
            "-b:v", f"{avg_bitrate}k",
            "-maxrate", f"{max_bitrate}k",
            "-minrate", f"{min_bitrate}k",
            "-bufsize", f"{avg_bitrate * 2}k",
            "-c:a", fmt_profile['audio_codec'],
            "-b:a", res_profile['audio_bitrate'],
            *fmt_profile.get('container_options', [])
        ]

        if fmt in ('mp4', 'hevc'):
            command.extend([
                "-preset", "fast" if res_profile['scale'] <= 480 else fmt_profile['preset'],
                "-crf", str(res_profile['crf']),
                "-profile:v", fmt_profile['profile'],
                "-tune", fmt_profile['tune'],
                "-x264-params" if fmt == 'mp4' else "-x265-params",
                "log-level=error:threads={}".format(min(4, self.thread_count))
            ])
        elif fmt == 'webm':
            command.extend([
                "-speed", "4" if res_profile['scale'] <= 480 else str(fmt_profile['speed']),
                "-row-mt", "1",
                "-quality", "good",
                "-crf", str(res_profile['crf']),
                "-threads", str(min(8, self.thread_count))
            ])

        if two_pass and res_profile['scale'] >= 720:  
            pass_log = self.output_path / f"ffmpeg2pass_{output_name}"
            
            pass1 = command + [
                "-pass", "1",
                "-passlogfile", str(pass_log),
                "-f", "null", "/dev/null"
            ]
            
            pass2 = command + [
                "-pass", "2",
                "-passlogfile", str(pass_log),
                str(output_path)
            ]
            
            if await self._run_ffmpeg_command(pass1, timeout=3600) and \
            await self._run_ffmpeg_command(pass2, timeout=3600):
                results[fmt].append(output_path)
                try:
                    (pass_log.with_suffix('.log')).unlink()
                    (pass_log.with_suffix('.log.mbtree')).unlink()
                except:
                    pass
        else:
            command.extend(["-y", str(output_path)])
            if await self._run_ffmpeg_command(command, timeout=3600):
                results[fmt].append(output_path)

        if output_path.exists():
            self._quick_quality_check(output_path, res_profile)

    def _quick_quality_check(self, output_path: Path, profile: dict):
        """Fast quality verification."""
        try:
            size_mb = output_path.stat().st_size / (1024 * 1024)
            if size_mb < profile['min_size_mb']:
                self.logger.warning(f"Small file size: {output_path.name} ({size_mb:.1f}MB)")
        except Exception as e:
            self.logger.error(f"Quality check failed: {str(e)}")
    
    async def split_video(self, input_path: Union[str, Path],
                        output_name: str,
                        cut_ranges: List[Tuple[float, float]]) -> Optional[List[Path]]:
        """
        Optimized video splitting with accurate cuts and proper audio sync.
        
        Args:
            input_path: Path to input video file
            output_name: Base name for output files
            cut_ranges: List of (start, end) time ranges in seconds
            
        Returns:
            List of output file paths or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        if not cut_ranges:
            self.logger.error("No cut ranges provided")
            return None

        validated_ranges = []
        for start, end in sorted((min(s,e), max(s,e)) for s,e in cut_ranges):
            if start >= end:
                continue
            validated_ranges.append((start, end))

        if not validated_ranges:
            self.logger.error("No valid cut ranges after validation")
            return None

        output_files = []
        output_ext = input_path.suffix or '.mp4'

        for i, (start, end) in enumerate(validated_ranges, 1):
            output_path = self.output_path / f"{output_name}_part{i:03d}{output_ext}"
            
            command = [
                self.ffmpeg_path,
                "-ss", str(start),
                "-i", str(input_path),
                "-to", str(end - start),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path)
            ]

            self.logger.info(f"Processing segment {i}: {start}s to {end}s")
            if not await self._run_ffmpeg_command(command, timeout=1800):
                self.logger.error(f"Failed to process segment {i}")
                continue

            if output_path.exists():
                output_files.append(output_path)
            else:
                self.logger.warning(f"Output file missing: {output_path}")

        return output_files if output_files else None
