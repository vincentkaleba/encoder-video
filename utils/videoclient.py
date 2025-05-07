import asyncio
from asyncio import subprocess
from collections import defaultdict
import re
import shlex
import subprocess 
import io
import json
import logging
import logging.handlers
import signal
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import magic 
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
    SRT = "SubRip Subtitle (SRT)"
    ASS = "Advanced SubStation Alpha (ASS)"
    SSA = "Advanced SubStation Alpha (SSA)"
    MOV_TEXT = "Movie Text (MOV_TEXT)"
    VOBSUB = "VobSub"
    PGS = "Presentation Graphic Stream (PGS)"
    TX3G = "Timed Text (TX3G)"
    WEBVTT = "Web Video Text Tracks (WEBVTT)"
    TEXT = "Plain Text"
    SUBRIP = "Subs"
    
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
        
        if logger.handlers:
            return logger
            
        logger.setLevel(logging.INFO)
        logger.propagate = False  
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        try:
            log_file = self.output_path / f"{self.name}.log"
            fh = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=5*1024*1024,
                backupCount=2          
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
    
    def _verify_ffmpeg(self):
            """Verify FFmpeg installation with minimal resource usage."""
            try:
                result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=5
                )
                self._ffmpeg_version = result.stdout.split('\n', 1)[0]
                self.logger.info(f"FFmpeg detected: {self._ffmpeg_version}")
            except subprocess.TimeoutExpired:
                self.logger.error("FFmpeg verification timed out")
                raise RuntimeError("FFmpeg verification failed") from None
            except Exception as e:
                self.logger.error(f"FFmpeg verification failed: {str(e)}")
                raise RuntimeError("FFmpeg is required for media processing") from e   
                     
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _handle_shutdown(self, signum, frame) -> None:
        """Handle shutdown signals with minimal processing."""
        self.logger.info(f"Received shutdown signal {signum}")
        self.stop()
    
    def start(self):
        if self.running:
            self.logger.info("VideoClient is already running.")
            return
        
        self.running = True
        self.logger.info("VideoClient started.")
        

        
    def stop(self) -> None:
        """Clean up resources efficiently."""
        if self.running:
            self.running = False
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.logger.info("Client shutdown complete")
            
    async def _run_ffmpeg_command(self, command: List[str], timeout: int = 3600) -> bool:
        """
        Run an FFmpeg command asynchronously with full output logging.
        
        Args:
            command: List of command arguments
            timeout: Maximum execution time in seconds
            
        Returns:
            bool: True if command succeeded, False otherwise
        """
        if not self.running:
            self.logger.warning("FFmpeg command skipped (processor not running)")
            return False

        # Log the complete command being executed
        self.logger.debug(f"Executing FFmpeg command: {' '.join(shlex.quote(arg) for arg in command)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,  # Capture stdout
                stderr=asyncio.subprocess.PIPE,  # Capture stderr
                limit=4 * 1024 * 1024  # Increased buffer size
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                
                # Decode outputs
                stdout_str = stdout.decode(errors='ignore').strip()
                stderr_str = stderr.decode(errors='ignore').strip()

                # Log all output
                if stdout_str:
                    self.logger.debug(f"FFmpeg stdout:\n{stdout_str}")
                if stderr_str:
                    self.logger.debug(f"FFmpeg stderr:\n{stderr_str}")

                if process.returncode != 0:
                    error_msg = stderr_str or stdout_str or "Unknown error"
                    self.logger.error(
                        f"FFmpeg failed with return code {process.returncode}:\n"
                        f"{error_msg[:1000]}{'...' if len(error_msg) > 1000 else ''}"
                    )
                    return False
                    
                return True

            except asyncio.TimeoutError:
                try:
                    process.terminate()  # Try gentle termination first
                    await asyncio.wait_for(process.wait(), timeout=5)
                except:
                    try:
                        process.kill()  # Force kill if needed
                        await process.wait()
                    except ProcessLookupError:
                        pass
                        
                self.logger.warning(f"FFmpeg command timed out after {timeout} seconds")
                return False

        except FileNotFoundError:
            self.logger.error("FFmpeg executable not found")
            return False
        except subprocess.SubprocessError as e:
            self.logger.error(f"Subprocess error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error running FFmpeg: {str(e)}", exc_info=True)
            return False
    
    async def get_media_info(self, file_path: Union[str, Path]) -> Optional[MediaFileInfo]:
        """
        Extract detailed media information using FFprobe.
        
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
                "ffprobe",
                "-v", "error",
                "-show_entries", 
                "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,channels,bit_rate,tags,disposition",
                "-show_streams", 
                "-of", "json",
                str(path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"FFprobe failed for {path.name}: {stderr.decode().strip()}")
                return None
                
            probe_data = json.loads(stdout.decode())
            
            # Create basic MediaFileInfo
            format_info = probe_data.get('format', {})
            streams = probe_data.get('streams', [])
            
            media_info = MediaFileInfo(
                path=path,
                size=int(format_info.get('size', stat.st_size)),
                duration=float(format_info.get('duration', 0)),
                media_type=MediaType.from_extension(path.suffix) or MediaType.MKV,
                bitrate=int(format_info.get('bit_rate', 0)) // 1000 if format_info.get('bit_rate') else 0
            )
            
            # Process video streams
            video_streams = [s for s in streams if s.get('codec_type') == 'video']
            if video_streams:
                video = video_streams[0]  # Take first video stream
                media_info.width = int(video.get('width', 0))
                media_info.height = int(video.get('height', 0))
                if not media_info.bitrate:
                    media_info.bitrate = int(video.get('bit_rate', 0)) // 1000
            
            # Process audio streams
            audio_index = 0
            for stream in [s for s in streams if s.get('codec_type') == 'audio']:
                audio_index += 1
                codec_name = stream.get('codec_name', '').upper()
                try:
                    codec = AudioCodec[codec_name]
                except KeyError:
                    codec = AudioCodec.AAC  # Default fallback
                
                tags = stream.get('tags', {})
                language = tags.get('language', 'und')  # 'und' for undefined
                
                disposition = stream.get('disposition', {})
                is_default = bool(disposition.get('default'))
                
                media_info.add_audio_track(AudioTrack(
                    index=audio_index,
                    language=language,
                    codec=codec,
                    channels=int(stream.get('channels', 2)),
                    is_default=is_default
                ))
            
            # Process subtitle streams
            sub_index = 0
            for stream in [s for s in streams if s.get('codec_type') == 'subtitle']:
                sub_index += 1
                codec_name = stream.get('codec_name', '').upper()
                try:
                    codec = SubtitleCodec[codec_name]
                except KeyError:
                    # Handle special cases for subtitle codecs
                    if stream.get('codec_name') == 'hdmv_pgs_subtitle':
                        codec = SubtitleCodec.PGS
                    elif stream.get('codec_name') == 'dvd_subtitle':
                        codec = SubtitleCodec.VOBSUB
                    else:
                        codec = SubtitleCodec.SRT  # Default fallback
                
                tags = stream.get('tags', {})
                language = tags.get('language', 'und')
                
                disposition = stream.get('disposition', {})
                is_default = bool(disposition.get('default'))
                is_forced = bool(disposition.get('forced'))
                
                media_info.add_subtitle_track(SubtitleTrack(
                    index=sub_index,
                    language=language,
                    codec=codec,
                    is_default=is_default,
                    is_forced=is_forced
                ))
            
            return media_info
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse FFprobe output for {path.name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error analyzing {path.name}: {str(e)}")
            
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
            index=(stream.get('audio_tracks', 0)) + 1, 
            language=stream.get('tags', {}).get('language', 'und'),
            codec=codec_map.get(codec_name, AudioCodec.AAC),
            channels=int(stream.get('channels', 2)),  
            is_default=bool(stream.get('disposition', {}).get('default', False))  
        )


    def _parse_subtitle_stream(self, stream: dict) -> SubtitleTrack:
        """Helper to parse subtitle stream data efficiently."""
        codec_name = stream.get('codec_name', '').lower()
        codec_map = {
            'mov_text': SubtitleCodec.MOV_TEXT,
            'srt': SubtitleCodec.SRT,
            'hdmv_pgs_subtitle': SubtitleCodec.PGS,
            'dvd_subtitle': SubtitleCodec.VOBSUB,
            'subrip': SubtitleCodec.SUBRIP,
            'ass': SubtitleCodec.ASS,        
            'ssa': SubtitleCodec.SSA    
        }
        
        disposition = stream.get('disposition', {})
        
        return SubtitleTrack(
            index=stream.get('index', 0) + 1, 
            language=stream.get('tags', {}).get('language', 'und'),
            codec=codec_map.get(codec_name, SubtitleCodec.SRT), 
            is_default=bool(disposition.get('default', False)),
            is_forced=bool(disposition.get('forced', False))   
        )

    

    async def extract_subtitles(self, input_path: Union[str, Path],
                            output_dir: Union[str, Path] = None) -> List[Path]:
        """
        Extract all subtitles from a video file with optimized resource usage.
        
        Args:
            input_path: Path to input video file
            output_dir: Directory to save subtitles (uses client output path if None)
            
        Returns:
            List of Paths to extracted subtitle files or empty list on failure
        """
        try:
            # Convert and validate paths
            input_path = Path(input_path)
            self.logger.debug(f"Starting subtitle extraction from: {input_path}")
            
            if not input_path.exists():
                self.logger.error(f"Input file does not exist: {input_path}")
                return []
                
            output_dir = Path(output_dir) if output_dir else self.output_path
            self.logger.debug(f"Output directory set to: {output_dir}")

            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.logger.error(f"Failed to create output directory {output_dir}: {str(e)}")
                return []

            # Get media info with error handling
            try:
                media_info = await self.get_media_info(input_path)
                print(media_info.subtitle_tracks)
                if not media_info:
                    self.logger.warning(f"Could not get media info for: {input_path}")
                    return []
                    
                self.logger.debug(f"Found {len(media_info.subtitle_tracks)} subtitle tracks")
                
                if not media_info.subtitle_tracks:
                    self.logger.info(f"No subtitles found in {input_path}")
                    return []
            except Exception as e:
                self.logger.error(f"Error analyzing media file: {str(e)}", exc_info=True)
                return []

            extracted_files = []
            base_name = input_path.stem
            tasks = []
            
            self.logger.debug(f"Preparing subtitle extraction tasks...")
            
            # Prepare all extraction commands
            for sub in media_info.subtitle_tracks:
                try:
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
                    self.logger.debug(f"Prepared extraction for track {sub.index} ({sub.language}) -> {output_path}")
                except Exception as e:
                    self.logger.error(f"Error preparing extraction for track {sub.index}: {str(e)}")

            # Execute all extraction commands
            for command, output_path in tasks:
                try:
                    self.logger.debug(f"Executing: {' '.join(command)}")
                    
                    if await self._run_ffmpeg_command(command, timeout=120):
                        extracted_files.append(output_path)
                        self.logger.debug(f"Successfully extracted subtitle: {output_path}")
                    else:
                        self.logger.warning(f"Failed to extract subtitle to {output_path}")
                except Exception as e:
                    self.logger.error(f"Error during subtitle extraction: {str(e)}", exc_info=True)

            if extracted_files:
                self.logger.info(f"Successfully extracted {len(extracted_files)}/{len(tasks)} subtitles from {input_path}")
            else:
                self.logger.warning(f"No subtitles were successfully extracted from {input_path}")

            return extracted_files

        except Exception as e:
            self.logger.error(f"Unexpected error in subtitle extraction: {str(e)}", exc_info=True)
            return []

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