import asyncio
from asyncio import subprocess
import re
import subprocess 
import io
import json
import logging
import logging.handlers
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import magic  # Ensure you have python-magic installed
from typing import Optional, List, Dict, Tuple, Callable, Union, Any, Iterator


class MediaType(Enum):
    """Enum for different types of video files with proper file extensions."""
    MP4 = "mp4"
    MKV = "mkv"
    AVI = "avi"
    MOV = "mov"
    WMV = "wmv"
    FLV = "flv"
    WEBM = "webm"
    MPEG = "mpeg"
    MPG = "mpg"
    TS = "ts"
    M2TS = "m2ts"
    M4V = "m4v"
    _3GP = "3gp"
    OGV = "ogv"
    ASF = "asf"
    RMVB = "rmvb"
    RM = "rm"
    DAT = "dat"
    MP3 = "mp3"
    AAC = "aac"
    OGG = "ogg"
    
    @classmethod
    def from_extension(cls, ext: str) -> Optional['MediaType']:
        """Get MediaType from file extension."""
        ext = ext.lower().lstrip('.')
        for member in cls:
            if member.value == ext:
                return member
        return None
        
    def __str__(self) -> str:
        return self.name


class AudioCodec(Enum):
    """Enum for different audio codecs with descriptions."""
    AAC = "Advanced Audio Coding"
    AC3 = "Dolby Digital"
    EAC3 = "Dolby Digital Plus"
    DTS = "Digital Theater Systems"
    DTSHD = "DTS-HD Master Audio"
    TRUEHD = "Dolby TrueHD"
    MP3 = "MPEG-1 Audio Layer III"
    FLAC = "Free Lossless Audio Codec"
    PCM = "Pulse Code Modulation"
    OPUS = "Opus"
    VORBIS = "Vorbis"
    
    @property
    def extension(self) -> str:
        """Get standard file extension for the audio codec."""
        return self.name.lower()
    
    def __str__(self) -> str:
        return self.name


class SubtitleCodec(Enum):
    """Enum for different subtitle codecs with descriptions."""
    SRT = "SubRip Text"
    SUBRIP = "SubRip (same as SRT)"
    TEXT = "Plain Text"
    ASS = "Advanced SubStation Alpha"
    VOBSUB = "VobSub"
    PGS = "Presentation Graphic Stream"
    TX3G = "Timed Text"
    WEBVTT = "Web Video Text Tracks"
    
    @property
    def extension(self) -> str:
        """Get standard file extension for the subtitle codec."""
        return self.name.lower()
    
    def __str__(self) -> str:
        return self.name


@dataclass
class SubtitleTrack:
    """Class to hold subtitle track information with validation."""
    index: int
    language: str  # Should ideally use standard language codes (ISO 639)
    codec: SubtitleCodec
    is_default: bool = False
    is_forced: bool = False
    stream_type: str = "text"
    
    def __post_init__(self):
        if not isinstance(self.codec, SubtitleCodec):
            raise ValueError("codec must be a SubtitleCodec enum member")
            
    def __str__(self) -> str:
        flags = []
        if self.is_default:
            flags.append("default")
        if self.is_forced:
            flags.append("forced")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        return f"Subtitle {self.index}: {self.language} [{self.codec}]{flag_str}"


@dataclass
class AudioTrack:
    """Class to hold audio track information with validation."""
    index: int
    language: str
    codec: AudioCodec
    channels: int = 2
    is_default: bool = False
    stream_type: str = "audio"
    
    def __post_init__(self):
        if not isinstance(self.codec, AudioCodec):
            raise ValueError("codec must be an AudioCodec enum member")
        if self.channels not in {1, 2, 6, 8}:
            logging.warning(f"Unusual channel count: {self.channels}")
            
    def __str__(self) -> str:
        default_flag = " (default)" if self.is_default else ""
        return f"Audio {self.index}: {self.language} [{self.codec}, {self.channels}ch]{default_flag}"


@dataclass
class MediaFileInfo:
    """Comprehensive media file information with proper typing and validation."""
    path: Path
    size: int  # in bytes
    duration: float  # in seconds
    media_type: MediaType
    width: int = 0
    height: int = 0
    bitrate: int = 0  # in kbps
    audio_tracks: List[AudioTrack] = field(default_factory=list)
    subtitle_tracks: List[SubtitleTrack] = field(default_factory=list)
    
    def __post_init__(self):
        if not isinstance(self.path, Path):
            self.path = Path(self.path)
        if not isinstance(self.media_type, MediaType):
            self.media_type = MediaType.from_extension(self.path.suffix) or MediaType.MKV
            
    @property
    def exists(self) -> bool:
        """Check if the file exists on disk."""
        return self.path.exists()
    
    @property
    def resolution(self) -> str:
        """Get resolution as string (e.g., '1920x1080')."""
        return f"{self.width}x{self.height}" if self.width and self.height else "Unknown"
    
    @property
    def formatted_duration(self) -> str:
        """Format duration as HH:MM:SS."""
        hours, remainder = divmod(int(self.duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @property
    def formatted_size(self) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size < 1024.0:
                return f"{self.size:.2f} {unit}"
            self.size /= 1024.0
        return f"{self.size:.2f} TB"
    
    # def __str__(self) -> str:
    #     return (
    #         f"Media File: {self.path.name}\n"
    #         f"Type: {self.media_type}\n"
    #         f"Size: {self.formatted_size}\n"
    #         f"Duration: {self.formatted_duration}\n"
    #         f"Resolution: {self.resolution}\n"
    #         f"Audio Tracks: {len(self.audio_tracks)}\n"
    #         f"Subtitle Tracks: {len(self.subtitle_tracks)}"
    #     )
    
    def add_audio_track(self, track: AudioTrack) -> None:
        """Add an audio track with validation."""
        if not isinstance(track, AudioTrack):
            raise ValueError("Must provide an AudioTrack object")
        self.audio_tracks.append(track)
    
    def add_subtitle_track(self, track: SubtitleTrack) -> None:
        """Add a subtitle track with validation."""
        if not isinstance(track, SubtitleTrack):
            raise ValueError("Must provide a SubtitleTrack object")
        self.subtitle_tracks.append(track)
    
    def get_default_audio(self) -> Optional[AudioTrack]:
        """Get the default audio track if available."""
        for track in self.audio_tracks:
            if track.is_default:
                return track
        return self.audio_tracks[0] if self.audio_tracks else None
    
    def get_forced_subtitles(self) -> Iterator[SubtitleTrack]:
        """Yield all forced subtitle tracks."""
        return (sub for sub in self.subtitle_tracks if sub.is_forced)

class VideoClient:
    """Optimized client for video processing with FFmpeg/FFprobe integration."""
    
    __slots__ = ['name', 'output_path', 'thread_count', 'ffmpeg_path', 'ffprobe_path',
                 'executor', 'logger', 'running', '_ffmpeg_version', '_ffprobe_version']
    
    def __init__(self, name: str, out_pth: str, trd: int = 5, 
                 ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        """
        Initialize the optimized VideoClient.
        
        Args:
            name: Identifier for this client instance
            out_pth: Output directory path for processed files
            trd: Number of worker threads (default: 5)
            ffmpeg: Path to ffmpeg executable (default: "ffmpeg")
            ffprobe: Path to ffprobe executable (default: "ffprobe")
        """
        self.name = name
        self.output_path = Path(out_pth)
        self.thread_count = max(1, min(trd, 20)) 
        self.ffmpeg_path = ffmpeg
        self.ffprobe_path = ffprobe
        self.running = False
        self._ffmpeg_version: Optional[str] = None
        self._ffprobe_version: Optional[str] = None
        
        # Setup components in optimal order
        self._setup_output_dir()
        self.logger = self._setup_optimized_logger()
        self._verify_ffmpeg()
        self._verify_ffprobe()
        self.executor = ThreadPoolExecutor(max_workers=self.thread_count)
        self._register_signal_handlers()
        
        
    def _setup_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Failed to create output directory: {e}") from e
        
    def _setup_optimized_logger(self) -> logging.Logger:
        """Configure and return an optimized logger instance."""
        logger = logging.getLogger(f"VideoClient_{hash(self.name)}")
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
            
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Prevent propagation to root logger
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler with rotation (only if output path is writable)
        try:
            log_file = self.output_path / f"{self.name}.log"
            fh = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=5*1024*1024,  # Reduced to 5MB
                backupCount=2           # Reduced backup count
            )
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except IOError as e:
            logger.warning(f"Could not set up file logging: {e}")
            
        return logger
        
    def _verify_ffprobe(self) -> None:
        """Verify FFprobe installation with minimal resource usage."""
        try:
            result = subprocess.run(
                [self.ffprobe_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=5
            )
            self._ffprobe_version = result.stdout.split('\n', 1)[0]
            self.logger.info(f"FFprobe detected: {self._ffprobe_version}")
        except subprocess.TimeoutExpired:
            self.logger.error("FFprobe verification timed out")
            raise RuntimeError("FFprobe verification failed") from None
        except Exception as e:
            self.logger.error(f"FFprobe verification failed: {str(e)}")
            raise RuntimeError("FFprobe is required for media analysis") from e
            
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals with minimal processing."""
        self.logger.info(f"Received shutdown signal {signum}")
        self.stop()
        
    def stop(self) -> None:
        """Clean up resources efficiently."""
        if self.running:
            self.running = False
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.logger.info("Client shutdown complete")
            
    async def _run_ffmpeg_command(self, command: List[str], timeout: int = 3600) -> bool:
        """
        Run an FFmpeg command asynchronously with optimized resource usage.
        
        Args:
            command: List of command arguments
            timeout: Maximum execution time in seconds
            
        Returns:
            bool: True if command succeeded, False otherwise
        """
        if not self.running:
            return False
            
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL, 
                stderr=asyncio.subprocess.PIPE,
                limit=1024*1024 
            )
            
            try:
                _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                if process.returncode != 0:
                    error_msg = stderr.decode(errors='ignore').strip()
                    if error_msg:
                        self.logger.error(f"FFmpeg failed: {error_msg[:200]}...")  
                    return False
                return True
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
                self.logger.warning("FFmpeg command timed out")
                return False
                
        except Exception as e:
            self.logger.error(f"Error running FFmpeg: {str(e)}", exc_info=True)
            return False
    
    async def get_media_info(self, file_path: Union[str, Path]) -> Optional[MediaFileInfo]:
        """
        Extract media information efficiently using FFprobe.
        
        Args:
            file_path: Path to media file
            
        Returns:
            MediaFileInfo object with metadata, or None if analysis fails
        """
        path = Path(file_path)
        if not path.exists():
            self.logger.error(f"File not found: {file_path}")
            return None
            
        try:
            stat = path.stat()
            
            command = [
                self.ffprobe_path,
                "-v", "error",
                "-show_entries",
                "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,channels,bit_rate,tags:stream_disposition=default,forced",
                "-of", "json",
                str(path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=512 * 1024  
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
                
                if process.returncode != 0:
                    error_msg = stderr.decode(errors='ignore').strip()
                    self.logger.error(f"FFprobe failed for {path.name}: {error_msg[:200]}...")
                    return None
                    
                probe_data = json.loads(stdout.decode())
                format_info = probe_data.get('format', {})
                streams = probe_data.get('streams', [])
                
                media_info = MediaFileInfo(
                    path=path,
                    size=int(format_info.get('size', stat.st_size)),
                    duration=float(format_info.get('duration', 0)),
                    media_type=MediaType.from_extension(path.suffix) or MediaType.MKV,
                    bitrate=int(format_info.get('bit_rate', 0)) // 1000 if format_info.get('bit_rate') else 0
                )
                
                for stream in streams:
                    codec_type = stream.get('codec_type')
                    
                    if codec_type == 'video' and not hasattr(media_info, 'width'):
                        media_info.width = int(stream.get('width', 0))
                        media_info.height = int(stream.get('height', 0))
                        if not media_info.bitrate and stream.get('bit_rate'):
                            media_info.bitrate = int(stream.get('bit_rate', 0)) // 1000
                    
                    elif codec_type == 'audio':
                        media_info.add_audio_track(self._parse_audio_stream(stream))
                    
                    elif codec_type == 'subtitle':
                        media_info.add_subtitle_track(self._parse_subtitle_stream(stream))
                
                return media_info
                
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
                self.logger.warning(f"FFprobe timeout for {path.name}")
                return None
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid FFprobe output for {path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error analyzing {path.name}", exc_info=True)
            
        return None

    def _parse_audio_stream(self, stream: dict) -> AudioTrack:
        """Helper to parse audio stream data efficiently."""
        codec_name = stream.get('codec_name', '').lower()
        codec_map = {
            'aac': AudioCodec.AAC,
            'ac3': AudioCodec.AC3,
            'eac3': AudioCodec.EAC3,
            'dts': AudioCodec.DTS,
            'mp3': AudioCodec.MP3,
            'opus': AudioCodec.OPUS
        }
        
        return AudioTrack(
            index=len(self.audio_tracks) + 1,
            language=stream.get('tags', {}).get('language', 'und'),
            codec=codec_map.get(codec_name, AudioCodec.AAC),
            channels=int(stream.get('channels', 2)),
            is_default=bool(stream.get('disposition', {}).get('default'))
        )

    def _parse_subtitle_stream(self, stream: dict) -> SubtitleTrack:
        """Helper to parse subtitle stream data efficiently."""
        codec_name = stream.get('codec_name', '').lower()
        codec_map = {
            'mov_text': SubtitleCodec.MOV_TEXT,
            'srt': SubtitleCodec.SRT,
            'hdmv_pgs_subtitle': SubtitleCodec.PGS,
            'dvd_subtitle': SubtitleCodec.VOBSUB
        }
        
        disposition = stream.get('disposition', {})
        return SubtitleTrack(
            index=len(self.subtitle_tracks) + 1,
            language=stream.get('tags', {}).get('language', 'und'),
            codec=codec_map.get(codec_name, SubtitleCodec.SRT),
            is_default=bool(disposition.get('default')),
            is_forced=bool(disposition.get('forced'))
        )
    

    async def extract_subtitles(self, input_path: Union[str, Path],
                            output_dir: Union[str, Path] = None) -> List[Path]:
        """
        Extract all subtitles from a video file with optimized resource usage.
        
        Args:
            input_path: Path to input video file
            output_dir: Directory to save subtitles (uses client output path if None)
            
        Returns:
            List of Paths to extracted subtitle files
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir) if output_dir else self.output_path
        output_dir.mkdir(parents=True, exist_ok=True)
        
        media_info = await self.get_media_info(input_path)
        if not media_info or not media_info.subtitle_tracks:
            self.logger.info(f"No subtitles found in {input_path.name}")
            return []
        
        extracted_files = []
        base_name = input_path.stem
        tasks = []
        
        for sub in media_info.subtitle_tracks:
            output_path = output_dir / f"{base_name}_{sub.language}_{sub.index}.{sub.codec.extension}"
            command = [
                self.ffmpeg_path,
                "-i", str(input_path),
                "-map", f"0:s:{sub.index-1}",
                "-c:s", "copy",
                "-y",
                str(output_path)
            ]
            tasks.append((command, output_path))
        
        for command, output_path in tasks:
            if await self._run_ffmpeg_command(command, timeout=120):
                extracted_files.append(output_path)
                self.logger.debug(f"Extracted subtitle: {output_path.name}")
        
        if extracted_files:
            self.logger.info(f"Extracted {len(extracted_files)} subtitles from {input_path.name}")
        return extracted_files

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
        Get specific chapter information by index.
        
        Args:
            input_path: Path to input media file
            chapter_index: Index of chapter to retrieve (1-based)
            
        Returns:
            Chapter dictionary or None if not found
        """
        chapters = await self.get_chapters(input_path)
        if not chapters:
            return None
            
        try:
            return chapters[chapter_index - 1]
        except IndexError:
            self.logger.error(f"Chapter index {chapter_index} out of range")
            return None
        

    @staticmethod
    def hms_to_seconds(hms: str) -> float:
        """Convert 'HH:MM:SS' into seconds (float)."""
        h, m, s = map(float, hms.split(':'))
        return h * 3600 + m * 60 + s

    async def add_chapters(self, input_path: Union[str, Path],
                            output_name: str,
                            chapters: List[Dict[str, Any]]) -> Optional[Path]:
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        metadata_file = self.output_path / "chapters.txt"
        try:
            with open(metadata_file, 'w') as f:
                f.write(";FFMETADATA1\n")
                for i, chapter in enumerate(chapters, 1):
                    f.write(
                        f"[CHAPTER]\n"
                        f"TIMEBASE=1/1000\n"
                        f"START={int(self.hms_to_seconds(chapter['start']) * 1000)}\n"
                        f"END={int(self.hms_to_seconds(chapter['end']) * 1000)}\n"
                        f"title={chapter.get('title', f'Chapter {i}')}\n\n"
                    )
        except Exception as e:
            self.logger.error(f"Failed to create chapter metadata: {str(e)}")
            return None

        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"

        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-i", str(metadata_file),
            "-map_metadata", "1",
            "-codec", "copy",
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Adding {len(chapters)} chapters to {input_path.name}")
        success = await self._run_ffmpeg_command(command)
        metadata_file.unlink()  # Clean up metadata file

        return output_path if success else None


    async def remove_chapters(self, input_path: Union[str, Path],
                            output_name: str) -> Optional[Path]:
        """
        Remove all chapters from a media file.
        
        Args:
            input_path: Path to input media file
            output_name: Name for output file (without extension)
            
        Returns:
            Path to output file without chapters, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"

        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-map_metadata", "-1",  # Remove all metadata
            "-codec", "copy",
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Removing chapters from {input_path.name}")
        return output_path if await self._run_ffmpeg_command(command) else None

    async def edit_chapter(self, input_path: Union[str, Path],
                         output_name: str,
                         chapter_index: int,
                         new_start: Optional[float] = None,
                         new_end: Optional[float] = None,
                         new_title: Optional[str] = None) -> Optional[Path]:
        """
        Edit a specific chapter in a media file.
        
        Args:
            input_path: Path to input media file
            output_name: Name for output file (without extension)
            chapter_index: Index of chapter to edit (1-based)
            new_start: New start time in seconds
            new_end: New end time in seconds
            new_title: New chapter title
            
        Returns:
            Path to output file with edited chapter, or None if failed
        """
        chapters = await self.get_chapters(input_path)
        if not chapters:
            return None

        try:
            chapter = chapters[chapter_index - 1]
            if new_start is not None:
                chapter['start'] = new_start
            if new_end is not None:
                chapter['end'] = new_end
            if new_title is not None:
                chapter['title'] = new_title

            return await self.add_chapters(input_path, output_name, chapters)
        except IndexError:
            self.logger.error(f"Chapter index {chapter_index} out of range")
            return None

    async def split_chapter(self, input_path: Union[str, Path],
                          output_name: str,
                          chapter_index: int,
                          split_time: float) -> Optional[Path]:
        """
        Split a chapter into two at the specified time.
        
        Args:
            input_path: Path to input media file
            output_name: Name for output file (without extension)
            chapter_index: Index of chapter to split (1-based)
            split_time: Time within chapter to split (in seconds)
            
        Returns:
            Path to output file with split chapter, or None if failed
        """
        chapters = await self.get_chapters(input_path)
        if not chapters:
            return None

        try:
            chapter = chapters[chapter_index - 1]
            if not (float(chapter['start']) < split_time < float(chapter['end'])):
                self.logger.error("Split time must be within chapter duration")
                return None

            # Create new chapters list with split chapter
            new_chapters = chapters[:chapter_index - 1]
            new_chapters.append({
                'start': chapter['start'],
                'end': split_time,
                'title': f"{chapter.get('title', 'Chapter')} Part 1"
            })
            new_chapters.append({
                'start': split_time,
                'end': chapter['end'],
                'title': f"{chapter.get('title', 'Chapter')} Part 2"
            })
            new_chapters.extend(chapters[chapter_index:])

            return await self.add_chapters(input_path, output_name, new_chapters)
        except IndexError:
            self.logger.error(f"Chapter index {chapter_index} out of range")
            return None

    async def trim_video(self, input_path: Union[str, Path],
                       output_name: str,
                       start_time: float,
                       end_time: float) -> Optional[Path]:
        """
        Trim video to specified time range.
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            Path to trimmed video file, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"

        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Trimming {input_path.name} from {start_time}s to {end_time}s")
        return output_path if await self._run_ffmpeg_command(command) else None

    async def cut_video(self, input_path: Union[str, Path],
                        output_name: str,
                        cut_ranges: List[Tuple[float, float]]) -> Optional[Path]:
        """
        Cut specified time ranges from video (inverse of trim).
        
        Args:
            input_path: Path to input video file
            output_name: Name for output file (without extension)
            cut_ranges: List of (start, end) time ranges to cut (in seconds)
            
        Returns:
            Path to cut video file, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        # Sort and merge overlapping ranges
        cut_ranges.sort()
        merged_ranges = []
        for current in cut_ranges:
            if not merged_ranges:
                merged_ranges.append(current)
            else:
                last = merged_ranges[-1]
                if current[0] <= last[1]:
                    new_last = (last[0], max(last[1], current[1]))
                    merged_ranges[-1] = new_last
                else:
                    merged_ranges.append(current)

        media_info = await self.get_media_info(input_path)
        duration = media_info.duration if media_info else float('inf')

        filter_complex_parts = []
        last_end = 0.0
        index = 0

        for start, end in merged_ranges:
            if last_end < start:
                filter_complex_parts.append(f"[0:v]trim=start={last_end}:end={start},setpts=PTS-STARTPTS[v{index}];")
                filter_complex_parts.append(f"[0:a]atrim=start={last_end}:end={start},asetpts=PTS-STARTPTS[a{index}];")
                index += 1
            last_end = end

        if last_end < duration:
            filter_complex_parts.append(f"[0:v]trim=start={last_end},setpts=PTS-STARTPTS[v{index}];")
            filter_complex_parts.append(f"[0:a]atrim=start={last_end},asetpts=PTS-STARTPTS[a{index}];")
            index += 1

        # Créer la commande concat propre
        video_audio_pairs = ''.join([f"[v{i}][a{i}]" for i in range(index)])
        concat_command = f"{video_audio_pairs}concat=n={index}:v=1:a=1[vout][aout]"

        filter_complex = ''.join(filter_complex_parts) + concat_command

        output_ext = input_path.suffix
        output_path = self.output_path / f"{output_name}{output_ext}"

        command = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-y",
            str(output_path)
        ]

        self.logger.info(f"Cutting {len(merged_ranges)} ranges from {input_path.name}")
        return output_path if await self._run_ffmpeg_command(command) else None

    
    async def concat_video(self, input_paths: List[Union[str, Path]],
                         output_name: str,
                         output_format: MediaType = MediaType.MP4,
                         transition_duration: float = 0.0) -> Optional[Path]:
        """
        Concatenate multiple video files into a single output file.
        
        Args:
            input_paths: List of paths to input video files
            output_name: Name for output file (without extension)
            output_format: Output file format (default: MP4)
            transition_duration: Duration of crossfade transition between clips (0 for no transition)
            
        Returns:
            Path to concatenated video file, or None if failed
        """
        if not input_paths:
            self.logger.error("No input files provided")
            return None

        # Verify all input files exist
        input_files = [Path(p) for p in input_paths]
        for file in input_files:
            if not file.exists():
                self.logger.error(f"Input file not found: {file}")
                return None

        output_path = self.output_path / f"{output_name}.{output_format.value}"

        if transition_duration <= 0:
            # Simple concatenation without transitions
            # Create a text file with the list of files
            list_file = self.output_path / "concat_list.txt"
            try:
                with open(list_file, 'w') as f:
                    for file in input_files:
                        f.write(f"file '{file.absolute()}'\n")
            except Exception as e:
                self.logger.error(f"Failed to create concat list: {str(e)}")
                return None

            command = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",  # Try stream copy first
                "-y",
                str(output_path)
            ]

            self.logger.info(f"Concatenating {len(input_files)} videos without transitions")
            success = await self._run_ffmpeg_command(command)
            list_file.unlink()  # Clean up
            
            if success:
                return output_path
            
            # If stream copy fails, try re-encoding
            self.logger.info("Stream copy failed, attempting re-encode")
            command = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-y",
                str(output_path)
            ]
            success = await self._run_ffmpeg_command(command)
            list_file.unlink()
            return output_path if success else None

        else:
            # Complex concatenation with transitions
            try:
                # First ensure all videos have same resolution and format
                media_infos = await asyncio.gather(*[self.get_media_info(f) for f in input_files])
                if not all(mi for mi in media_infos):
                    self.logger.error("Failed to get media info for all files")
                    return None

                # Build complex filter
                filter_complex = []
                inputs = []
                overlay_inputs = []
                last_output = None

                for i, (file, mi) in enumerate(zip(input_files, media_infos)):
                    inputs.extend(["-i", str(file)])
                    
                    # Scale all inputs to same resolution (use first file's resolution)
                    if i == 0:
                        target_width = mi.width
                        target_height = mi.height
                        filter_complex.append(
                            f"[{i}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2[v{i}];"
                        )
                    else:
                        filter_complex.append(
                            f"[{i}:v]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2[v{i}];"
                        )
                    
                    # Audio handling
                    filter_complex.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}];")
                    
                    # Transition logic
                    if i > 0:
                        transition_frames = int(transition_duration * 30) 
                        filter_complex.append(
                            f"[last][v{i}]overlay=enable='between(t,{mi.duration-transition_duration},{mi.duration})':"
                            f"x='(W-w)*t/{transition_duration}'[vout{i}];"
                        )
                        last_output = f"[vout{i}]"
                    else:
                        last_output = f"[v{i}]"

                # Audio concatenation
                filter_complex.append(f"{''.join([f'[a{i}]' for i in range(len(input_files))])}concat=n={len(input_files)}:v=0:a=1[audio]")

                command = [
                    self.ffmpeg_path,
                    *inputs,
                    "-filter_complex", "".join(filter_complex),
                    "-map", f"{last_output}",
                    "-map", "[audio]",
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-y",
                    str(output_path)
                ]

                self.logger.info(f"Concatenating {len(input_files)} videos with {transition_duration}s transitions")
                return output_path if await self._run_ffmpeg_command(command) else None

            except Exception as e:
                self.logger.error(f"Error during concatenation with transitions: {str(e)}")
                return None
    
    RESOLUTION_PROFILES = {
        '144p': {
            'scale': 144,
            'video_bitrate': (150, 300),  
            'audio_bitrate': '64k',
            'min_size_mb': 5,
            'crf': 32  
        },
        '240p': {
            'scale': 240,
            'video_bitrate': (300, 600),
            'audio_bitrate': '64k',
            'min_size_mb': 10,
            'crf': 28
        },
        '360p': {
            'scale': 360,
            'video_bitrate': (600, 1000),
            'audio_bitrate': '96k',
            'min_size_mb': 20,
            'crf': 26
        },
        '480p': {
            'scale': 480,
            'video_bitrate': (1000, 1500),
            'audio_bitrate': '96k',
            'min_size_mb': 30,
            'crf': 24
        },
        '720p': {
            'scale': 720,
            'video_bitrate': (1500, 3000),
            'audio_bitrate': '128k',
            'min_size_mb': 50,
            'crf': 22
        },
        '1080p': {
            'scale': 1080,
            'video_bitrate': (3000, 6000),
            'audio_bitrate': '128k',
            'min_size_mb': 80,
            'crf': 20
        }
    }

    FORMAT_PROFILES = {
        'mp4': {
            'video_codec': 'libx264',
            'audio_codec': 'aac',
            'extension': 'mp4',
            'preset': 'slow',  
            'tune': 'film',   
            'profile': 'high',
            'level': '4.0',
            'container_options': ['-movflags', '+faststart']
        },
        'hevc': {
            'video_codec': 'libx265',
            'audio_codec': 'aac',
            'extension': 'mp4',
            'preset': 'medium',
            'tune': 'ssim',    
            'profile': 'main10',
            'container_options': ['-tag:v', 'hvc1']
        },
        'webm': {
            'video_codec': 'libvpx-vp9',
            'audio_codec': 'libopus',
            'extension': 'webm',
            'speed': 2,        
            'quality': 'good',
            'row-mt': 1        
        },
        'mkv': {  
            'video_codec': 'libx264',
            'audio_codec': 'aac',
            'extension': 'mkv',
            'preset': 'slow',
            'container_options': []
        },
    }
    async def compress_video(self, input_path: Union[str, Path],
                        output_basename: str,
                        target_formats: List[str] = ['mp4', 'hevc'],
                        keep_original_quality: bool = False,
                        two_pass: bool = False) -> Dict[str, List[Path]]:
        """
        Generate high-quality compressed versions of a video.
        
        Args:
            input_path: Path to input video file
            output_basename: Base name for output files
            target_formats: Formats to generate (mp4, hevc, webm)
            keep_original_quality: Keep original resolution versions
            two_pass: Use two-pass encoding for better quality (slower)
            
        Returns:
            Dictionary of generated files by format
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return {}

        # Get video metadata
        media_info = await self.get_media_info(input_path)
        if not media_info:
            self.logger.error(f"Could not get media info for: {input_path}")
            return {}

        original_height = media_info.height
        if original_height == 0:
            self.logger.error("Could not determine original video height")
            return {}

        # Determine which resolutions to generate
        resolutions = []
        for name, profile in self.RESOLUTION_PROFILES.items():
            if profile['scale'] < original_height or (keep_original_quality and profile['scale'] == original_height):
                resolutions.append((name, profile))

        # Sort from lowest to highest resolution
        resolutions.sort(key=lambda x: x[1]['scale'])

        results = {fmt: [] for fmt in target_formats if fmt in self.FORMAT_PROFILES}

        # Process each format and resolution
        for fmt in target_formats:
            if fmt not in self.FORMAT_PROFILES:
                self.logger.warning(f"Skipping unsupported format: {fmt}")
                continue

            fmt_profile = self.FORMAT_PROFILES[fmt]
            self.logger.info(f"Processing format: {fmt}")

            for res_name, res_profile in resolutions:
                output_name = f"{output_basename}_{res_name}"
                output_path = self.output_path / f"{output_name}.{fmt_profile['extension']}"

                # Calculate average bitrate
                avg_bitrate = sum(res_profile['video_bitrate']) / 2

                # Base FFmpeg command
                command = [
                    self.ffmpeg_path,
                    "-i", str(input_path),
                    "-vf", f"scale=-2:{res_profile['scale']}",
                    "-c:v", fmt_profile['video_codec'],
                    "-b:v", f"{avg_bitrate}k",
                    "-maxrate", f"{res_profile['video_bitrate'][1]}k",
                    "-minrate", f"{res_profile['video_bitrate'][0]}k",
                    "-bufsize", f"{avg_bitrate * 2}k",
                    "-c:a", fmt_profile['audio_codec'],
                    "-b:a", res_profile['audio_bitrate'],
                    *fmt_profile.get('container_options', [])
                ]

                # Codec-specific optimizations
                if fmt == 'mp4' or fmt == 'hevc':
                    command.extend([
                        "-preset", fmt_profile['preset'],
                        "-crf", str(res_profile['crf']),
                        "-profile:v", fmt_profile['profile'],
                        "-tune", fmt_profile['tune'],
                        "-x264-params" if fmt == 'mp4' else "-x265-params",
                        "log-level=error"
                    ])
                elif fmt == 'webm':
                    command.extend([
                        "-speed", str(fmt_profile['speed']),
                        "-row-mt", str(fmt_profile['row-mt']),
                        "-quality", fmt_profile['quality'],
                        "-crf", str(res_profile['crf'])
                    ])

                # Two-pass encoding if requested
                if two_pass:
                    pass1 = [*command, "-pass", "1", "-f", "null", "/dev/null"]
                    pass2 = [*command, "-pass", "2", str(output_path)]
                    
                    self.logger.info(f"Starting 2-pass encoding for {res_name} {fmt}")
                    if await self._run_ffmpeg_command(pass1) and await self._run_ffmpeg_command(pass2):
                        results[fmt].append(output_path)
                else:
                    command.extend(["-y", str(output_path)])
                    self.logger.info(f"Creating {res_name} version in {fmt} format")
                    if await self._run_ffmpeg_command(command):
                        results[fmt].append(output_path)

                # Verify output quality
                if output_path.exists():
                    self._verify_output_quality(input_path, output_path, res_profile)

        return results

    def _verify_output_quality(self, original: Path, compressed: Path, profile: dict):
        """Verify output video meets quality standards."""
        try:
            # Check file size meets minimum
            size_mb = compressed.stat().st_size / (1024 * 1024)
            if size_mb < profile['min_size_mb']:
                self.logger.warning(f"File too small: {compressed.name} ({size_mb:.1f}MB < {profile['min_size_mb']}MB)")
            
            # TODO: Add PSNR/SSIM/VMAF quality metrics checks
            # This would require additional FFmpeg analysis
            
        except Exception as e:
            self.logger.error(f"Quality verification failed: {str(e)}")
    
    async def split_video(self, input_path: Union[str, Path],
                        output_name: str,
                        cut_ranges: List[Tuple[float, float]]) -> Optional[List[Path]]:
        """
        Split a video into multiple segments based on specified time ranges.
        
        Args:
            input_path: Path to input video file
            output_name: Base name for output files
            cut_ranges: List of (start, end) time ranges to split (in seconds)
            
        Returns:
            List of paths to split video files, or None if failed
        """
        input_path = Path(input_path)
        if not input_path.exists():
            self.logger.error(f"Input file not found: {input_path}")
            return None

        # Sort and merge overlapping ranges
        cut_ranges.sort()
        merged_ranges = []
        for current in cut_ranges:
            if not merged_ranges:
                merged_ranges.append(current)
            else:
                last = merged_ranges[-1]
                if current[0] <= last[1]:
                    new_last = (last[0], max(last[1], current[1]))
                    merged_ranges[-1] = new_last
                else:
                    merged_ranges.append(current)

        media_info = await self.get_media_info(input_path)
        duration = media_info.duration if media_info else float('inf')

        output_files = []

        for i, (start, end) in enumerate(merged_ranges):
            if start >= duration or end > duration:
                self.logger.error("Start or end time exceeds video duration")
                continue

            output_ext = input_path.suffix
            output_path = self.output_path / f"{output_name}_part{i+1}{output_ext}"

            command = [
                self.ffmpeg_path,
                "-i", str(input_path),
                "-ss", str(start),
                "-to", str(end),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(output_path)
            ]

            self.logger.info(f"Splitting {input_path.name} from {start}s to {end}s")
            if await self._run_ffmpeg_command(command):
                output_files.append(output_path)

        return output_files if output_files else None
    