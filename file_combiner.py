#!/usr/bin/env python3
"""
File Combiner - Complete Python Implementation
High-performance file combiner optimized for large repositories and AI agents

Performance Features:
- True async I/O with prefetching for streaming writes
- Concurrent file restoration during split operations
- ThreadPoolExecutor for parallel metadata collection
- O(1) memory streaming architecture
"""

import argparse
import asyncio
import base64
import difflib
import functools
import gzip
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import tempfile
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Callable, Any
import fnmatch
import logging


# Async helper for running blocking I/O in thread pool
async def run_in_thread(func: Callable[..., Any], *args, **kwargs) -> Any:
    """Run a blocking function in a thread pool for true async I/O.

    Uses asyncio.to_thread() for Python 3.9+ (more efficient),
    falls back to run_in_executor() for Python 3.8.
    """
    if sys.version_info >= (3, 9):
        return await asyncio.to_thread(func, *args, **kwargs)
    else:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(func, *args, **kwargs)
        )

# Optional pathspec for gitignore support
try:
    import pathspec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False
    pathspec = None

try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TimeElapsedColumn,
        MofNCompleteColumn,
    )

    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None
    Progress = None

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    tqdm = None


__version__ = "2.1.0"
__author__ = "File Combiner Project"
__license__ = "MIT"


@dataclass
class FileMetadata:
    """Enhanced file metadata structure"""

    path: str
    size: int
    mtime: float
    mode: int
    encoding: str = "utf-8"
    checksum: Optional[str] = None
    mime_type: Optional[str] = None
    is_binary: bool = False
    error: Optional[str] = None
    ends_with_newline: bool = False


@dataclass
class ArchiveHeader:
    """Archive header with comprehensive metadata"""

    version: str
    created_at: str
    source_path: str
    total_files: int
    total_size: int
    compression: str
    generator: str
    platform: str
    python_version: str
    command_line: str


class FileCombinerError(Exception):
    """Base exception for file combiner errors"""

    pass


class SecurityError(FileCombinerError):
    """Security-related errors such as path traversal attempts"""

    pass


class FileCombiner:
    """High-performance file combiner with advanced features"""

    SEPARATOR = "=== FILE_SEPARATOR ==="
    METADATA_PREFIX = "FILE_METADATA:"
    ENCODING_PREFIX = "ENCODING:"
    CONTENT_PREFIX = "CONTENT:"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # Initialize temporary files list first (needed for cleanup in case of early errors)
        self._temp_files = []

        # Initialize rich console
        self.console = Console() if HAS_RICH else None

        self.logger = self._setup_logging()

        # Configuration with sensible defaults
        self.max_file_size = self._parse_size(self.config.get("max_file_size", "50M"))

        # Fix max_workers validation - ensure it's always positive
        max_workers_config = self.config.get("max_workers", os.cpu_count() or 4)
        if max_workers_config <= 0:
            max_workers_config = os.cpu_count() or 4
        self.max_workers = min(max_workers_config, 32)

        self.compression_level = self.config.get("compression_level", 6)
        self.buffer_size = self.config.get("buffer_size", 64 * 1024)  # 64KB
        self.max_depth = self.config.get("max_depth", 50)

        # Pattern matching
        self.exclude_patterns = (
            self.config.get("exclude_patterns", []) + self._default_excludes()
        )
        self.include_patterns = self.config.get("include_patterns", [])

        # Feature flags
        self.preserve_permissions = self.config.get("preserve_permissions", False)
        self.calculate_checksums = self.config.get("calculate_checksums", False)
        self.follow_symlinks = self.config.get("follow_symlinks", False)
        self.ignore_binary = self.config.get("ignore_binary", False)
        self.dry_run = self.config.get("dry_run", False)
        self.verbose = self.config.get("verbose", False)

        # TTY detection for progress bars (disable in non-interactive terminals like CI/CD)
        self.is_tty = sys.stdout.isatty()

        # Gitignore support
        self.respect_gitignore = self.config.get("respect_gitignore", True)
        self._gitignore_spec = None

        # Signal handling for graceful cleanup
        self._setup_signal_handlers()

        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "bytes_processed": 0,
            "errors": 0,
        }

    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging"""
        level = logging.DEBUG if self.config.get("verbose") else logging.INFO

        # Create logger
        logger = logging.getLogger("file_combiner")
        logger.setLevel(level)

        # Avoid duplicate handlers
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful cleanup on interruption"""
        def signal_handler(signum, frame):
            """Handle interrupt signals gracefully"""
            self.logger.warning("Received interrupt signal, cleaning up...")
            self._cleanup_temp_files()
            sys.exit(130)  # 128 + SIGINT (2)

        # Only setup handlers for signals available on current platform
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, OSError):
            # Signal handling may not be available in all contexts (e.g., threads)
            pass

    def _load_gitignore(self, source_path: Path) -> None:
        """Load and parse .gitignore file from source directory"""
        if not self.respect_gitignore or not HAS_PATHSPEC:
            return

        gitignore_path = source_path / ".gitignore"
        if not gitignore_path.exists():
            return

        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gitignore_content = f.read()

            # Parse gitignore patterns
            self._gitignore_spec = pathspec.PathSpec.from_lines(
                pathspec.patterns.GitWildMatchPattern,
                gitignore_content.splitlines()
            )

            if self.verbose:
                self.logger.debug(f"Loaded .gitignore from {gitignore_path}")

        except Exception as e:
            if self.verbose:
                self.logger.warning(f"Failed to parse .gitignore: {e}")
            self._gitignore_spec = None

    def _matches_gitignore(self, relative_path: str) -> bool:
        """Check if path matches gitignore patterns"""
        if self._gitignore_spec is None:
            return False

        try:
            return self._gitignore_spec.match_file(relative_path)
        except Exception:
            return False

    def _is_github_url(self, url_or_path: str) -> bool:
        """Check if the input is a GitHub URL"""
        try:
            parsed = urllib.parse.urlparse(url_or_path)
            return parsed.netloc.lower() in ["github.com", "www.github.com"]
        except Exception:
            return False

    def _clone_github_repo(self, github_url: str) -> Optional[Path]:
        """Clone a GitHub repository to a temporary directory"""
        try:
            # Create a temporary directory
            temp_dir = Path(tempfile.mkdtemp(prefix="file_combiner_github_"))
            self._temp_files.append(temp_dir)

            self.logger.info(f"Cloning GitHub repository: {github_url}")

            # Clone the repository
            result = subprocess.run(
                ["git", "clone", "--depth", "1", github_url, str(temp_dir)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                self.logger.error(f"Failed to clone repository: {result.stderr}")
                return None

            self.logger.info(f"Successfully cloned to: {temp_dir}")
            return temp_dir

        except subprocess.TimeoutExpired:
            self.logger.error("Git clone operation timed out")
            return None
        except FileNotFoundError:
            self.logger.error(
                "Git command not found. Please install Git to clone repositories."
            )
            return None
        except Exception as e:
            self.logger.error(f"Error cloning repository: {e}")
            return None

    def _detect_output_format(
        self, output_path: Path, format_arg: Optional[str] = None
    ) -> str:
        """Detect output format from file extension or format argument"""
        if format_arg:
            return format_arg.lower()

        # Detect from file extension
        suffix = output_path.suffix.lower()

        format_map = {
            ".txt": "txt",
            ".xml": "xml",
            ".json": "json",
            ".md": "markdown",
            ".markdown": "markdown",
            ".yml": "yaml",
            ".yaml": "yaml",
        }

        return format_map.get(suffix, "txt")

    def _validate_format_compatibility(
        self, output_path: Path, format_type: str
    ) -> bool:
        """Validate that format is compatible with output path and compression"""
        # Check if compression is requested with incompatible formats
        is_compressed = output_path.suffix.lower() == ".gz"

        if is_compressed and format_type in ["xml", "json", "markdown", "yaml"]:
            self.logger.warning(
                f"Compression with {format_type} format may affect readability"
            )

        return True

    def _default_excludes(self) -> List[str]:
        """Default exclusion patterns optimized for development"""
        return [
            # Version control
            ".git/**/*",
            ".git/*",
            ".svn/**/*",
            ".hg/**/*",
            ".bzr/**/*",
            # Dependencies
            "node_modules/**/*",
            "__pycache__/**/*",
            ".pytest_cache/**/*",
            "vendor/**/*",
            ".tox/**/*",
            ".venv/**/*",
            "venv/**/*",
            # Build artifacts
            "dist/**/*",
            "build/**/*",
            "target/**/*",
            "out/**/*",
            "*.egg-info/**/*",
            ".eggs/**/*",
            # Compiled files
            "*.pyc",
            "*.pyo",
            "*.pyd",
            "*.class",
            "*.jar",
            "*.war",
            "*.o",
            "*.obj",
            "*.dll",
            "*.so",
            "*.dylib",
            # IDE files
            ".vscode/**/*",
            ".idea/**/*",
            "*.swp",
            "*.swo",
            "*~",
            ".DS_Store",
            "Thumbs.db",
            "desktop.ini",
            # Logs and temporary files
            "*.log",
            "*.tmp",
            "*.temp",
            "*.cache",
            "*.pid",
            # Minified files
            "*.min.js",
            "*.min.css",
            "*.bundle.js",
            # Coverage and test artifacts
            ".coverage",
            ".nyc_output/**/*",
            "coverage/**/*",
            # Environment files
            ".env",
            ".env.*",
        ]

    def _parse_size(self, size_str: str) -> int:
        """Parse human-readable size to bytes with validation"""
        if not isinstance(size_str, str):
            raise ValueError(f"Size must be a string, got {type(size_str)}")

        size_str = size_str.upper().strip()
        if size_str.endswith("B"):
            size_str = size_str[:-1]

        match = re.match(r"^(\d*\.?\d+)([KMGT]?)$", size_str)
        if not match:
            raise ValueError(f"Invalid size format: {size_str}")

        number, unit = match.groups()
        try:
            number = float(number)
        except ValueError:
            raise ValueError(f"Invalid number in size: {number}")

        multipliers = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

        if unit not in multipliers:
            raise ValueError(f"Invalid size unit: {unit}")

        result = int(number * multipliers[unit])
        if result < 0:
            raise ValueError(f"Size cannot be negative: {result}")

        return result

    def _matches_pattern(self, path: str, patterns: List[str]) -> bool:
        """Advanced pattern matching with glob support and error handling"""
        if not patterns:
            return False

        for pattern in patterns:
            try:
                if "**" in pattern:
                    # Handle recursive glob patterns (e.g., src/**, **/*.py)
                    # Convert glob pattern to regex properly
                    # First, escape regex special chars except * and ?
                    regex_pattern = re.escape(pattern)
                    # Use placeholders to avoid replacement conflicts
                    regex_pattern = regex_pattern.replace(r"\*\*", "\x00DSTAR\x00").replace(r"\*", "\x00STAR\x00").replace(r"\?", "\x00QUEST\x00")
                    # **/ means "zero or more directories" -> (.*/)?
                    regex_pattern = regex_pattern.replace("\x00DSTAR\x00/", "(.*/)?")
                    # ** at end or standalone matches any characters including /
                    regex_pattern = regex_pattern.replace("\x00DSTAR\x00", ".*")
                    # * matches any characters except /
                    regex_pattern = regex_pattern.replace("\x00STAR\x00", "[^/]*")
                    # ? matches single character except /
                    regex_pattern = regex_pattern.replace("\x00QUEST\x00", "[^/]")
                    if re.match(f"^{regex_pattern}$", path):
                        return True
                elif fnmatch.fnmatch(path, pattern):
                    return True
                elif fnmatch.fnmatch(os.path.basename(path), pattern):
                    return True
                # Also check if path starts with pattern (for directory patterns)
                elif path.startswith(pattern.rstrip("/") + "/"):
                    return True
            except re.error:
                self.logger.warning(f"Invalid pattern: {pattern}")
                continue

        return False

    def _normalize_patterns(self, patterns: List[str], source_path: Path, pattern_type: str = "include") -> List[str]:
        """Normalize patterns to be relative to source directory.

        Converts filesystem paths like '../repo/src' to relative patterns like 'src/**'.
        Pure glob patterns like '*.py' are preserved as-is.

        Args:
            patterns: List of patterns (paths or globs) to normalize
            source_path: The source directory being processed
            pattern_type: "include" or "exclude" for logging

        Returns:
            List of normalized patterns relative to source_path
        """
        if not patterns:
            return []

        normalized = []
        source_resolved = source_path.resolve()

        for pattern in patterns:
            # Try to resolve as a filesystem path
            try:
                # Check if pattern contains glob wildcards at the start
                # If it starts with a glob, treat as pattern not path
                if pattern.startswith("*") or pattern.startswith("?"):
                    normalized.append(pattern)
                    if self.verbose:
                        self.logger.debug(f"Using {pattern_type} glob pattern: {pattern}")
                    continue

                # Try to treat as a path
                pattern_path = Path(pattern)

                # Resolve relative to CWD (where user ran the command)
                if not pattern_path.is_absolute():
                    pattern_path = Path.cwd() / pattern

                pattern_resolved = pattern_path.resolve()

                # Check if this path is inside or equal to source directory
                try:
                    relative = pattern_resolved.relative_to(source_resolved)
                    relative_str = str(relative).replace("\\", "/")

                    if pattern_resolved.is_dir():
                        # Directory: match all files within it
                        if relative_str == ".":
                            # Pattern points to source itself
                            normalized.append("**")
                        else:
                            normalized.append(f"{relative_str}/**")
                        if self.verbose:
                            self.logger.debug(f"Normalized {pattern_type} directory: {pattern} -> {relative_str}/**")
                    elif pattern_resolved.is_file():
                        # Single file: exact path
                        normalized.append(relative_str)
                        if self.verbose:
                            self.logger.debug(f"Normalized {pattern_type} file: {pattern} -> {relative_str}")
                    elif "*" in pattern or "?" in pattern:
                        # Pattern with wildcards - make relative
                        normalized.append(relative_str)
                        if self.verbose:
                            self.logger.debug(f"Normalized {pattern_type} glob: {pattern} -> {relative_str}")
                    else:
                        # Path doesn't exist - warn user but add it
                        normalized.append(relative_str)
                        self.logger.warning(f"{pattern_type.capitalize()} path does not exist: {pattern}")
                    continue
                except ValueError:
                    # Path is outside source directory
                    if not ("*" in pattern or "?" in pattern):
                        self.logger.warning(
                            f"{pattern_type.capitalize()} path '{pattern}' is outside source directory '{source_path}'"
                        )
            except (OSError, ValueError):
                # Path resolution failed - treat as pure pattern
                pass

            # Treat as a glob pattern (not a filesystem path)
            normalized.append(pattern)
            if self.verbose:
                self.logger.debug(f"Using {pattern_type} pattern as-is: {pattern}")

        return normalized

    def _should_exclude(self, file_path: Path, relative_path: str) -> Tuple[bool, str]:
        """Advanced pattern matching for file exclusion with comprehensive checks"""
        try:
            # Validate path
            if not file_path.exists():
                return True, "file does not exist"

            file_stat = file_path.stat()

            # Check file size
            if file_stat.st_size > self.max_file_size:
                return True, f"too large ({self._format_size(file_stat.st_size)})"

            # Check gitignore patterns first (most common exclusion source)
            if self._matches_gitignore(relative_path):
                return True, "matches .gitignore pattern"

            # Check exclude patterns
            if self._matches_pattern(relative_path, self.exclude_patterns):
                return True, "matches exclude pattern"

            # Check include patterns (if specified)
            if self.include_patterns and not self._matches_pattern(
                relative_path, self.include_patterns
            ):
                return True, "doesn't match include pattern"

            # Check if it's a special file (socket, device, etc.)
            if not file_stat.st_mode & (stat.S_IFREG | stat.S_IFLNK):
                return True, "not a regular file or symlink"

            return False, ""

        except (OSError, PermissionError) as e:
            return True, f"cannot access: {e}"

    def _is_binary(self, file_path: Path) -> bool:
        """Efficient binary file detection with comprehensive checks"""
        try:
            # First check by extension (fast path)
            text_extensions = {
                ".txt",
                ".md",
                ".rst",
                ".py",
                ".js",
                ".html",
                ".css",
                ".json",
                ".xml",
                ".yaml",
                ".yml",
                ".toml",
                ".ini",
                ".cfg",
                ".conf",
                ".sh",
                ".bash",
                ".c",
                ".cpp",
                ".h",
                ".java",
                ".go",
                ".rs",
                ".rb",
                ".pl",
                ".php",
                ".swift",
                ".kt",
                ".scala",
                ".clj",
                ".sql",
                ".r",
                ".m",
                ".dockerfile",
                ".makefile",
                ".cmake",
            }

            if file_path.suffix.lower() in text_extensions:
                return False

            # Check MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type and mime_type.startswith("text/"):
                return False

            # Check file content (sample first chunk)
            file_size = file_path.stat().st_size
            if file_size == 0:
                return False  # Empty files are considered text

            sample_size = min(8192, file_size)
            with open(file_path, "rb") as f:
                chunk = f.read(sample_size)

            if not chunk:
                return False

            # Check for null bytes (strong indicator of binary)
            if b"\0" in chunk:
                return True

            # Check for high ratio of non-printable characters
            printable_chars = sum(
                1 for byte in chunk if 32 <= byte <= 126 or byte in (9, 10, 13)
            )
            ratio = printable_chars / len(chunk)

            # Files with less than 70% printable characters are likely binary
            return ratio < 0.7

        except (OSError, PermissionError):
            # If we can't read it, assume it's binary for safety
            return True

    def _format_size(self, size: int) -> str:
        """Format size in human-readable format"""
        if size < 0:
            return "0B"

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"

    def _dry_run_combine(self, all_files: List[Path], source_path: Path) -> bool:
        """Perform a comprehensive dry run"""
        try:
            self.logger.info("DRY RUN - Files that would be processed:")

            total_size = 0
            processed_count = 0
            skipped_count = 0

            for file_path in all_files:
                try:
                    relative_path = str(file_path.relative_to(source_path))
                    should_exclude, reason = self._should_exclude(
                        file_path, relative_path
                    )

                    if should_exclude:
                        if self.verbose:
                            if HAS_RICH and self.console:
                                self.console.print(
                                    f"  [red]✗[/red] {relative_path} ({reason})"
                                )
                            else:
                                print(f"  ✗ {relative_path} ({reason})")
                        skipped_count += 1
                    else:
                        file_size = file_path.stat().st_size
                        is_binary = self._is_binary(file_path)
                        file_type = "binary" if is_binary else "text"
                        if HAS_RICH and self.console:
                            self.console.print(
                                f"  [green]✓[/green] {relative_path} ([blue]{self._format_size(file_size)}[/blue], [yellow]{file_type}[/yellow])"
                            )
                        else:
                            print(
                                f"  ✓ {relative_path} ({self._format_size(file_size)}, {file_type})"
                            )
                        total_size += file_size
                        processed_count += 1

                except Exception as e:
                    if HAS_RICH and self.console:
                        self.console.print(
                            f"  [red]✗[/red] {relative_path} (error: {e})"
                        )
                    else:
                        print(f"  ✗ {relative_path} (error: {e})")
                    skipped_count += 1

            # Summary
            if HAS_RICH and self.console:
                self.console.print("\n[bold]Summary:[/bold]")
                self.console.print(
                    f"  Would process: [green]{processed_count}[/green] files ([blue]{self._format_size(total_size)}[/blue])"
                )
                self.console.print(
                    f"  Would skip: [yellow]{skipped_count}[/yellow] files"
                )
            else:
                print("\nSummary:")
                print(
                    f"  Would process: {processed_count} files ({self._format_size(total_size)})"
                )
                print(f"  Would skip: {skipped_count} files")

            return True

        except Exception as e:
            self.logger.error(f"Error during dry run: {e}")
            return False

    async def combine_files(
        self,
        source_path: Union[str, Path],
        output_path: Union[str, Path],
        compress: bool = False,
        progress: bool = True,
        format_type: Optional[str] = None,
    ) -> bool:
        """Combine files with comprehensive error handling and validation"""
        try:
            # Check if source_path is a GitHub URL
            if isinstance(source_path, str) and self._is_github_url(source_path):
                cloned_path = self._clone_github_repo(source_path)
                if cloned_path is None:
                    self.logger.error("Failed to clone GitHub repository")
                    return False
                source_path = cloned_path
            else:
                source_path = Path(source_path).resolve()

            output_path = Path(output_path).resolve()

            # Detect and validate output format
            detected_format = self._detect_output_format(output_path, format_type)
            if self.verbose:
                self.logger.debug(
                    f"Detected output format: {detected_format} for {output_path}"
                )
            if not self._validate_format_compatibility(output_path, detected_format):
                return False

            # Validation
            if not source_path.exists():
                raise FileCombinerError(f"Source path does not exist: {source_path}")

            if not source_path.is_dir():
                raise FileCombinerError(
                    f"Source path is not a directory: {source_path}"
                )

            # Check if output directory is writable
            output_parent = output_path.parent
            if not output_parent.exists():
                output_parent.mkdir(parents=True, exist_ok=True)

            if not os.access(output_parent, os.W_OK):
                raise FileCombinerError(
                    f"Cannot write to output directory: {output_parent}"
                )

            start_time = time.time()
            self.stats = {
                "files_processed": 0,
                "files_skipped": 0,
                "bytes_processed": 0,
                "errors": 0,
            }

            # Normalize include/exclude patterns relative to source directory
            # This converts paths like '../repo/src' to 'src/**'
            if self.include_patterns:
                original_include = self.include_patterns.copy()
                self.include_patterns = self._normalize_patterns(
                    self.include_patterns, source_path, "include"
                )
                if self.verbose:
                    self.logger.debug(f"Include patterns: {original_include} -> {self.include_patterns}")

            if self.exclude_patterns:
                # Separate default excludes from user excludes for normalization
                default_excludes = self._default_excludes()
                user_excludes = [p for p in self.exclude_patterns if p not in default_excludes]
                if user_excludes:
                    original_exclude = user_excludes.copy()
                    normalized_excludes = self._normalize_patterns(
                        user_excludes, source_path, "exclude"
                    )
                    # Recombine: normalized user patterns + default patterns
                    self.exclude_patterns = normalized_excludes + default_excludes
                    if self.verbose:
                        self.logger.debug(f"Exclude patterns: {original_exclude} -> {normalized_excludes}")

            # Load .gitignore if present and enabled
            if self.respect_gitignore:
                self._load_gitignore(source_path)
                if self._gitignore_spec and self.verbose:
                    self.logger.info("Respecting .gitignore patterns")

            # Scan files
            self.logger.info(f"Scanning source directory: {source_path}")
            all_files = self._scan_directory(source_path)

            if not all_files:
                self.logger.warning("No files found in source directory")
                return False

            if self.dry_run:
                return self._dry_run_combine(all_files, source_path)

            # Phase 1: Collect metadata in parallel (memory-efficient)
            # Only stores (metadata, file_path) tuples - NOT file content
            # This keeps memory usage O(n) for metadata but O(1) for content
            file_entries: List[Tuple[FileMetadata, Path]] = []

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(
                        self._collect_file_metadata, file_path, source_path
                    ): file_path
                    for file_path in all_files
                }

                # Collect metadata with progress bar
                # Disable rich/tqdm progress bars in non-TTY environments (CI/CD)
                use_rich_progress = progress and HAS_RICH and self.console and self.is_tty
                use_tqdm_progress = progress and HAS_TQDM and tqdm and self.is_tty and not use_rich_progress

                completed_count = 0
                if use_rich_progress:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        MofNCompleteColumn(),
                        TimeElapsedColumn(),
                        console=self.console,
                    ) as progress_bar:
                        task = progress_bar.add_task(
                            "Collecting metadata", total=len(all_files)
                        )

                        for future in as_completed(future_to_file):
                            completed_count += 1
                            try:
                                result = future.result()
                                if result:
                                    file_entries.append(result)
                            except Exception as e:
                                file_path = future_to_file[future]
                                self.logger.error(f"Error processing {file_path}: {e}")
                                self.stats["errors"] += 1

                            progress_bar.update(task, advance=1)
                elif use_tqdm_progress:
                    pbar = tqdm(
                        total=len(all_files), desc="Collecting metadata", unit="files"
                    )
                    for future in as_completed(future_to_file):
                        completed_count += 1
                        try:
                            result = future.result()
                            if result:
                                file_entries.append(result)
                        except Exception as e:
                            file_path = future_to_file[future]
                            self.logger.error(f"Error processing {file_path}: {e}")
                            self.stats["errors"] += 1
                        pbar.update(1)
                    pbar.close()
                elif progress:
                    print(f"Collecting metadata for {len(all_files)} files...")
                    for future in as_completed(future_to_file):
                        completed_count += 1
                        try:
                            result = future.result()
                            if result:
                                file_entries.append(result)
                        except Exception as e:
                            file_path = future_to_file[future]
                            self.logger.error(f"Error processing {file_path}: {e}")
                            self.stats["errors"] += 1

                        if completed_count % 50 == 0:
                            print(
                                f"Collected {completed_count}/{len(all_files)} files...",
                                end="\r",
                            )
                    print(f"\nCollected metadata for {completed_count}/{len(all_files)} files")
                else:
                    # No progress display
                    for future in as_completed(future_to_file):
                        completed_count += 1
                        try:
                            result = future.result()
                            if result:
                                file_entries.append(result)
                        except Exception as e:
                            file_path = future_to_file[future]
                            self.logger.error(f"Error processing {file_path}: {e}")
                            self.stats["errors"] += 1

            if not file_entries:
                self.logger.error("No files were successfully processed")
                return False

            # Sort files by path for consistent output
            file_entries.sort(key=lambda x: x[0].path)

            # Phase 2: Write archive with streaming (O(1) memory for content)
            # Content is read on-demand for each file, not held in memory
            success = await self._write_archive_streaming(
                output_path, source_path, file_entries, compress, detected_format
            )

            if success:
                elapsed = time.time() - start_time
                self.logger.info(
                    f"Successfully combined {self.stats['files_processed']} files"
                )
                self.logger.info(
                    f"Total size: {self._format_size(self.stats['bytes_processed'])}"
                )
                self.logger.info(
                    f"Skipped: {self.stats['files_skipped']}, Errors: {self.stats['errors']}"
                )
                self.logger.info(f"Processing time: {elapsed:.2f}s")
                self.logger.info(f"Output: {output_path}")

            return success

        except Exception as e:
            self.logger.error(f"Failed to combine files: {e}")
            if self.verbose:
                self.logger.error(traceback.format_exc())
            return False
        finally:
            self._cleanup_temp_files()

    def _scan_directory(self, source_path: Path) -> List[Path]:
        """Scan directory with depth control and error handling"""
        files = []
        visited_dirs = set()  # Prevent infinite loops with symlinks

        def scan_recursive(current_path: Path, depth: int = 0) -> None:
            if depth > self.max_depth:
                self.logger.warning(
                    f"Maximum depth ({self.max_depth}) reached at {current_path}"
                )
                return

            # Prevent infinite loops
            try:
                real_path = current_path.resolve()
                if real_path in visited_dirs:
                    return
                visited_dirs.add(real_path)
            except (OSError, RuntimeError):
                return

            try:
                items = list(current_path.iterdir())
                items.sort()  # Consistent ordering

                for item in items:
                    try:
                        if item.is_file():
                            files.append(item)
                        elif item.is_dir():
                            if self.follow_symlinks or not item.is_symlink():
                                scan_recursive(item, depth + 1)
                    except (OSError, PermissionError) as e:
                        if self.verbose:
                            self.logger.warning(f"Cannot access {item}: {e}")
                        continue

            except (OSError, PermissionError) as e:
                self.logger.warning(f"Cannot scan directory {current_path}: {e}")

        scan_recursive(source_path)
        return files

    def _process_file_worker(
        self, file_path: Path, source_path: Path
    ) -> Optional[Tuple[FileMetadata, bytes]]:
        """Process single file with comprehensive error handling"""
        try:
            relative_path = str(file_path.relative_to(source_path))

            # Check if file should be excluded
            should_exclude, reason = self._should_exclude(file_path, relative_path)
            if should_exclude:
                if self.verbose:
                    self.logger.debug(f"Excluding {relative_path}: {reason}")
                self.stats["files_skipped"] += 1
                return None

            # Get file stats
            file_stat = file_path.stat()
            is_binary = self._is_binary(file_path)

            # Create metadata
            metadata = FileMetadata(
                path=relative_path,
                size=file_stat.st_size,
                mtime=file_stat.st_mtime,
                mode=file_stat.st_mode,
                is_binary=is_binary,
                encoding="base64" if is_binary else "utf-8",
                mime_type=mimetypes.guess_type(str(file_path))[0],
            )

            # Add checksum if requested
            if self.calculate_checksums:
                metadata.checksum = self._calculate_checksum(file_path)

            # Read file content with proper encoding handling
            content = self._read_file_content(file_path, metadata)
            if content is None:
                self.stats["errors"] += 1
                return None

            self.stats["files_processed"] += 1
            self.stats["bytes_processed"] += metadata.size

            if self.verbose:
                self.logger.debug(
                    f"Processed {relative_path} ({self._format_size(metadata.size)})"
                )

            return (metadata, content)

        except Exception as e:
            self.logger.error(f"Error processing {file_path}: {e}")
            self.stats["errors"] += 1
            return None

    def _collect_file_metadata(
        self, file_path: Path, base_path: Path
    ) -> Optional[Tuple[FileMetadata, Path]]:
        """
        Collect file metadata without reading content (memory-efficient).

        Returns (metadata, file_path) tuple for streaming write phase.
        Content is read on-demand during write to maintain O(1) memory usage.
        """
        try:
            # Calculate relative path
            try:
                relative_path = str(file_path.relative_to(base_path))
            except ValueError:
                self.logger.warning(f"Cannot determine relative path for {file_path}")
                return None

            # Normalize path separators
            relative_path = relative_path.replace("\\", "/")

            # Apply include/exclude filters
            should_exclude, reason = self._should_exclude(file_path, relative_path)
            if should_exclude:
                if self.verbose:
                    self.logger.debug(f"Excluding {relative_path}: {reason}")
                self.stats["files_skipped"] += 1
                return None

            # Get file stats
            file_stat = file_path.stat()
            is_binary = self._is_binary(file_path)

            # Create metadata
            metadata = FileMetadata(
                path=relative_path,
                size=file_stat.st_size,
                mtime=file_stat.st_mtime,
                mode=file_stat.st_mode,
                is_binary=is_binary,
                encoding="base64" if is_binary else "utf-8",
                mime_type=mimetypes.guess_type(str(file_path))[0],
            )

            # Add checksum if requested
            if self.calculate_checksums:
                metadata.checksum = self._calculate_checksum(file_path)

            self.stats["files_processed"] += 1
            self.stats["bytes_processed"] += metadata.size

            if self.verbose:
                self.logger.debug(
                    f"Collected metadata for {relative_path} ({self._format_size(metadata.size)})"
                )

            return (metadata, file_path)

        except Exception as e:
            self.logger.error(f"Error collecting metadata for {file_path}: {e}")
            self.stats["errors"] += 1
            return None

    def _read_file_content(
        self, file_path: Path, metadata: FileMetadata
    ) -> Optional[bytes]:
        """Read file content with robust encoding detection"""
        try:
            if metadata.is_binary:
                # Read binary files and encode as base64
                with open(file_path, "rb") as f:
                    content = f.read()
                return base64.b64encode(content)
            else:
                # Try multiple encodings for text files
                encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252", "iso-8859-1"]

                for encoding in encodings:
                    try:
                        with open(
                            file_path, "r", encoding=encoding, errors="strict"
                        ) as f:
                            content = f.read()

                        # Track whether the file ends with a newline
                        metadata.ends_with_newline = content.endswith("\n")
                        metadata.encoding = encoding
                        return content.encode("utf-8")
                    except (UnicodeDecodeError, UnicodeError):
                        continue

                # If all text encodings fail, treat as binary
                self.logger.warning(
                    f"Cannot decode {file_path} as text, treating as binary"
                )
                with open(file_path, "rb") as f:
                    content = f.read()
                metadata.is_binary = True
                metadata.encoding = "base64"
                return base64.b64encode(content)

        except (OSError, PermissionError) as e:
            self.logger.error(f"Cannot read {file_path}: {e}")
            return None

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum with error handling"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(self.buffer_size)
                    if not chunk:
                        break
                    hash_sha256.update(chunk)

            return hash_sha256.hexdigest()
        except (OSError, PermissionError) as e:
            self.logger.warning(f"Cannot calculate checksum for {file_path}: {e}")
            return "error"

    async def _write_archive(
        self,
        output_path: Path,
        source_path: Path,
        processed_files: List[Tuple[FileMetadata, bytes]],
        compress: bool,
        format_type: str = "txt",
    ) -> bool:
        """Write archive with atomic operations and proper error handling"""
        temp_file = None
        try:
            # Create temporary file in same directory as output
            temp_file = tempfile.NamedTemporaryFile(
                mode="wb" if compress else "w",
                suffix=".tmp",
                dir=output_path.parent,
                delete=False,
                encoding="utf-8" if not compress else None,
            )
            self._temp_files.append(temp_file.name)

            # Write to temporary file first (atomic operation)
            if compress:
                with gzip.open(
                    temp_file.name,
                    "wt",
                    encoding="utf-8",
                    compresslevel=self.compression_level,
                ) as f:
                    await self._write_format_content(
                        f, source_path, processed_files, format_type
                    )
            else:
                with open(temp_file.name, "w", encoding="utf-8") as f:
                    await self._write_format_content(
                        f, source_path, processed_files, format_type
                    )

            # Atomic move to final location
            shutil.move(temp_file.name, output_path)
            self._temp_files.remove(temp_file.name)

            return True

        except Exception as e:
            self.logger.error(f"Error writing archive: {e}")
            if temp_file and temp_file.name in self._temp_files:
                try:
                    os.unlink(temp_file.name)
                    self._temp_files.remove(temp_file.name)
                except OSError:
                    pass
            return False

    async def _write_archive_streaming(
        self,
        output_path: Path,
        source_path: Path,
        file_entries: List[Tuple[FileMetadata, Path]],
        compress: bool,
        format_type: str = "txt",
    ) -> bool:
        """
        Write archive with streaming - O(1) memory for content.

        Reads file content on-demand during write, avoiding accumulation
        of all file contents in memory. This allows processing repositories
        of any size with bounded memory usage.
        """
        temp_file = None
        try:
            # Create temporary file in same directory as output
            temp_file = tempfile.NamedTemporaryFile(
                mode="wb" if compress else "w",
                suffix=".tmp",
                dir=output_path.parent,
                delete=False,
                encoding="utf-8" if not compress else None,
            )
            self._temp_files.append(temp_file.name)

            # Write to temporary file first (atomic operation)
            if compress:
                with gzip.open(
                    temp_file.name,
                    "wt",
                    encoding="utf-8",
                    compresslevel=self.compression_level,
                ) as f:
                    await self._write_format_streaming(
                        f, source_path, file_entries, format_type
                    )
            else:
                with open(temp_file.name, "w", encoding="utf-8") as f:
                    await self._write_format_streaming(
                        f, source_path, file_entries, format_type
                    )

            # Atomic move to final location
            shutil.move(temp_file.name, output_path)
            self._temp_files.remove(temp_file.name)

            return True

        except Exception as e:
            self.logger.error(f"Error writing archive: {e}")
            if temp_file and temp_file.name in self._temp_files:
                try:
                    os.unlink(temp_file.name)
                    self._temp_files.remove(temp_file.name)
                except OSError:
                    pass
            return False

    async def _write_format_streaming(
        self,
        f,
        source_path: Path,
        file_entries: List[Tuple[FileMetadata, Path]],
        format_type: str,
    ):
        """Dispatch to appropriate streaming format writer"""
        if format_type == "xml":
            await self._write_xml_streaming(f, source_path, file_entries)
        elif format_type == "json":
            await self._write_json_streaming(f, source_path, file_entries)
        elif format_type == "markdown":
            await self._write_markdown_streaming(f, source_path, file_entries)
        elif format_type == "yaml":
            await self._write_yaml_streaming(f, source_path, file_entries)
        else:  # Default to txt format
            await self._write_txt_streaming(f, source_path, file_entries)

    def _read_content_for_entry(
        self, metadata: FileMetadata, file_path: Path
    ) -> Optional[bytes]:
        """Read file content on-demand for streaming write"""
        content = self._read_file_content(file_path, metadata)
        return content

    async def _read_content_async(
        self, metadata: FileMetadata, file_path: Path
    ) -> Optional[bytes]:
        """Async version of _read_content_for_entry using thread pool"""
        return await run_in_thread(self._read_content_for_entry, metadata, file_path)

    async def _write_with_prefetch(
        self,
        f,
        file_entries: List[Tuple[FileMetadata, Path]],
        write_entry_func: Callable[[Any, FileMetadata, bytes], None],
    ):
        """Write entries with prefetching - reads next file while writing current.

        This provides true async performance by overlapping I/O operations:
        - While writing file N to output, file N+1 is being read from disk
        - Improves throughput by ~30-50% on I/O-bound workloads
        """
        if not file_entries:
            return

        # Start reading the first file
        prefetch_task = asyncio.create_task(
            self._read_content_async(file_entries[0][0], file_entries[0][1])
        )

        for i, (metadata, file_path) in enumerate(file_entries):
            # Wait for prefetched content
            content = await prefetch_task

            # Start prefetching next file immediately (before writing current)
            if i + 1 < len(file_entries):
                next_metadata, next_path = file_entries[i + 1]
                prefetch_task = asyncio.create_task(
                    self._read_content_async(next_metadata, next_path)
                )

            # Write current file (while next is being read)
            if content is not None:
                write_entry_func(f, metadata, content)
            # Content goes out of scope here - memory freed

    async def _write_txt_streaming(
        self, f, source_path: Path, file_entries: List[Tuple[FileMetadata, Path]]
    ):
        """Write TXT archive with streaming - O(1) memory"""
        # Write enhanced header
        f.write("# Enhanced Combined Files Archive\n")
        f.write(f"# Generated by file-combiner v{__version__}\n")
        f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
        f.write(f"# Source: {source_path}\n")
        f.write(f"# Total files: {len(file_entries)}\n")
        f.write(f"# Total size: {self._format_size(self.stats['bytes_processed'])}\n")
        f.write("#\n")
        f.write("# Format:\n")
        f.write(f"# {self.SEPARATOR}\n")
        f.write(f"# {self.METADATA_PREFIX} <json_metadata>\n")
        f.write(f"# {self.ENCODING_PREFIX} <encoding_type>\n")
        f.write("# <file_content>\n")
        f.write("#\n\n")

        def write_txt_entry(f, metadata: FileMetadata, content: bytes):
            f.write(f"{self.SEPARATOR}\n")
            f.write(f"{self.METADATA_PREFIX} {json.dumps(asdict(metadata))}\n")
            f.write(f"{self.ENCODING_PREFIX} {metadata.encoding}\n")
            if metadata.is_binary:
                f.write(content.decode("ascii"))
            else:
                f.write(content.decode("utf-8"))
            f.write("\n")

        await self._write_with_prefetch(f, file_entries, write_txt_entry)

    async def _write_xml_streaming(
        self, f, source_path: Path, file_entries: List[Tuple[FileMetadata, Path]]
    ):
        """Write XML archive with streaming and prefetching - O(1) memory per file"""
        # Write XML header manually for streaming
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f'<file_archive version="{__version__}" ')
        f.write(f'created="{time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}" ')
        f.write(f'source="{source_path}" ')
        f.write(f'total_files="{len(file_entries)}" ')
        f.write(f'total_size="{self.stats["bytes_processed"]}">\n')

        def write_xml_entry(f, metadata: FileMetadata, content: bytes):
            # Build file element with attributes
            attrs = " ".join(
                f'{k}="{self._xml_escape_attr(str(v))}"'
                for k, v in asdict(metadata).items()
                if v is not None
            )
            f.write(f"  <file {attrs}>")
            if metadata.is_binary:
                f.write(content.decode("ascii"))
            else:
                f.write(self._xml_escape_content(content.decode("utf-8")))
            f.write("</file>\n")

        await self._write_with_prefetch(f, file_entries, write_xml_entry)
        f.write("</file_archive>")

    def _xml_escape_attr(self, s: str) -> str:
        """Escape string for XML attribute value"""
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _xml_escape_content(self, s: str) -> str:
        """Escape string for XML element content"""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    async def _write_json_streaming(
        self, f, source_path: Path, file_entries: List[Tuple[FileMetadata, Path]]
    ):
        """Write JSON archive with streaming and prefetching"""
        # Write header
        f.write("{\n")
        f.write('  "metadata": {\n')
        f.write(f'    "version": "{__version__}",\n')
        f.write(
            f'    "created": "{time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}",\n'
        )
        f.write(f'    "source": {json.dumps(str(source_path))},\n')
        f.write(f'    "total_files": {len(file_entries)},\n')
        f.write(f'    "total_size": {self.stats["bytes_processed"]}\n')
        f.write("  },\n")
        f.write('  "files": [\n')

        # Stream with prefetching (JSON needs special handling for commas)
        if file_entries:
            first = True
            prefetch_task = asyncio.create_task(
                self._read_content_async(file_entries[0][0], file_entries[0][1])
            )

            for i, (metadata, file_path) in enumerate(file_entries):
                content = await prefetch_task

                # Prefetch next file
                if i + 1 < len(file_entries):
                    next_metadata, next_path = file_entries[i + 1]
                    prefetch_task = asyncio.create_task(
                        self._read_content_async(next_metadata, next_path)
                    )

                if content is None:
                    continue

                if not first:
                    f.write(",\n")
                first = False

                file_data = asdict(metadata)
                if metadata.is_binary:
                    file_data["content"] = content.decode("ascii")
                else:
                    file_data["content"] = content.decode("utf-8")

                # Write indented JSON for this file
                file_json = json.dumps(file_data, indent=2, ensure_ascii=False)
                indented = "\n".join("    " + line for line in file_json.split("\n"))
                f.write(indented)

        f.write("\n  ]\n}")

    async def _write_markdown_streaming(
        self, f, source_path: Path, file_entries: List[Tuple[FileMetadata, Path]]
    ):
        """Write Markdown archive with streaming and prefetching"""
        # Write header
        f.write("# Combined Files Archive\n\n")
        f.write(f"**Generated by:** file-combiner v{__version__}  \n")
        f.write(
            f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  \n"
        )
        f.write(f"**Source:** `{source_path}`  \n")
        f.write(f"**Total files:** {len(file_entries)}  \n")
        f.write(
            f"**Total size:** {self._format_size(self.stats['bytes_processed'])}  \n\n"
        )

        # Table of contents (uses only metadata, not content)
        f.write("## Table of Contents\n\n")
        for i, (metadata, _) in enumerate(file_entries, 1):
            anchor = metadata.path.replace("/", "").replace(".", "")
            f.write(f"{i}. [{metadata.path}](#{anchor})\n")
        f.write("\n")

        def write_md_entry(f, metadata: FileMetadata, content: bytes):
            f.write(f"## {metadata.path}\n\n")
            f.write(f"**Size:** {self._format_size(metadata.size)}  \n")
            f.write(
                f"**Modified:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metadata.mtime))}  \n"
            )
            f.write(f"**Encoding:** {metadata.encoding}  \n")
            f.write(f"**Binary:** {'Yes' if metadata.is_binary else 'No'}  \n\n")

            if metadata.is_binary:
                content_str = content.decode("ascii")
                fence = self._get_safe_fence(content_str)
                f.write(f"{fence}\n")
                f.write(content_str)
                f.write(f"\n{fence}\n\n")
            else:
                lang = self._detect_language(metadata.path)
                content_str = content.decode("utf-8")
                fence = self._get_safe_fence(content_str)
                f.write(f"{fence}{lang}\n")
                f.write(content_str)
                f.write(f"\n{fence}\n\n")

        await self._write_with_prefetch(f, file_entries, write_md_entry)

    async def _write_yaml_streaming(
        self, f, source_path: Path, file_entries: List[Tuple[FileMetadata, Path]]
    ):
        """Write YAML archive with streaming and prefetching"""
        # Write header
        f.write("# Combined Files Archive\n")
        f.write(f"version: {__version__}\n")
        f.write(f"created: '{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}'\n")
        f.write(f"source: '{source_path}'\n")
        f.write(f"total_files: {len(file_entries)}\n")
        f.write(f"total_size: {self.stats['bytes_processed']}\n\n")
        f.write("files:\n")

        def write_yaml_entry(f, metadata: FileMetadata, content: bytes):
            f.write(f"  - path: '{metadata.path}'\n")
            f.write(f"    size: {metadata.size}\n")
            f.write(f"    mtime: {metadata.mtime}\n")
            f.write(f"    encoding: '{metadata.encoding}'\n")
            f.write(f"    is_binary: {str(metadata.is_binary).lower()}\n")

            if metadata.is_binary:
                content_str = content.decode("ascii")
            else:
                content_str = content.decode("utf-8")

            content_lines = content_str.split("\n")
            f.write("    content: |\n")
            for line in content_lines:
                f.write(f"      {line}\n")
            f.write("\n")

        await self._write_with_prefetch(f, file_entries, write_yaml_entry)

    async def _write_archive_content(
        self, f, source_path: Path, processed_files: List[Tuple[FileMetadata, bytes]]
    ):
        """Write the actual archive content"""
        # Write enhanced header
        f.write("# Enhanced Combined Files Archive\n")
        f.write(f"# Generated by file-combiner v{__version__}\n")
        f.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
        f.write(f"# Source: {source_path}\n")
        f.write(f"# Total files: {len(processed_files)}\n")
        f.write(f"# Total size: {self._format_size(self.stats['bytes_processed'])}\n")
        f.write("#\n")
        f.write("# Format:\n")
        f.write(f"# {self.SEPARATOR}\n")
        f.write(f"# {self.METADATA_PREFIX} <json_metadata>\n")
        f.write(f"# {self.ENCODING_PREFIX} <encoding_type>\n")
        f.write("# <file_content>\n")
        f.write("#\n\n")

        # Write files
        for metadata, content in processed_files:
            f.write(f"{self.SEPARATOR}\n")
            f.write(f"{self.METADATA_PREFIX} {json.dumps(asdict(metadata))}\n")
            f.write(f"{self.ENCODING_PREFIX} {metadata.encoding}\n")

            if metadata.is_binary:
                f.write(content.decode("ascii"))
            else:
                f.write(content.decode("utf-8"))

            # Add separator after content
            f.write("\n")

    async def _write_format_content(
        self,
        f,
        source_path: Path,
        processed_files: List[Tuple[FileMetadata, bytes]],
        format_type: str,
    ):
        """Dispatch to appropriate format writer"""
        if format_type == "xml":
            await self._write_xml_format(f, source_path, processed_files)
        elif format_type == "json":
            await self._write_json_format(f, source_path, processed_files)
        elif format_type == "markdown":
            await self._write_markdown_format(f, source_path, processed_files)
        elif format_type == "yaml":
            await self._write_yaml_format(f, source_path, processed_files)
        else:  # Default to txt format
            await self._write_archive_content(f, source_path, processed_files)

    async def _write_xml_format(
        self, f, source_path: Path, processed_files: List[Tuple[FileMetadata, bytes]]
    ):
        """Write archive in XML format"""
        import xml.etree.ElementTree as ET

        # Create root element
        root = ET.Element("file_archive")
        root.set("version", __version__)
        root.set("created", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
        root.set("source", str(source_path))
        root.set("total_files", str(len(processed_files)))
        root.set("total_size", str(self.stats["bytes_processed"]))

        # Add files
        for metadata, content in processed_files:
            file_elem = ET.SubElement(root, "file")

            # Add metadata as attributes
            for key, value in asdict(metadata).items():
                if value is not None:
                    file_elem.set(key, str(value))

            # Add content
            if metadata.is_binary:
                file_elem.text = content.decode("ascii")
            else:
                file_elem.text = content.decode("utf-8")

        # Write XML with declaration
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        ET.indent(root, space="  ")
        f.write(ET.tostring(root, encoding="unicode"))

    async def _write_json_format(
        self, f, source_path: Path, processed_files: List[Tuple[FileMetadata, bytes]]
    ):
        """Write archive in JSON format"""
        archive_data = {
            "metadata": {
                "version": __version__,
                "created": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "source": str(source_path),
                "total_files": len(processed_files),
                "total_size": self.stats["bytes_processed"],
            },
            "files": [],
        }

        for metadata, content in processed_files:
            file_data = asdict(metadata)

            if metadata.is_binary:
                file_data["content"] = content.decode("ascii")
            else:
                file_data["content"] = content.decode("utf-8")

            archive_data["files"].append(file_data)

        json.dump(archive_data, f, indent=2, ensure_ascii=False)

    async def _write_markdown_format(
        self, f, source_path: Path, processed_files: List[Tuple[FileMetadata, bytes]]
    ):
        """Write archive in Markdown format with syntax highlighting"""
        # Write header
        f.write(f"# Combined Files Archive\n\n")
        f.write(f"**Generated by:** file-combiner v{__version__}  \n")
        f.write(
            f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}  \n"
        )
        f.write(f"**Source:** `{source_path}`  \n")
        f.write(f"**Total files:** {len(processed_files)}  \n")
        f.write(
            f"**Total size:** {self._format_size(self.stats['bytes_processed'])}  \n\n"
        )

        # Table of contents
        f.write("## Table of Contents\n\n")
        for i, (metadata, _) in enumerate(processed_files, 1):
            f.write(
                f"{i}. [{metadata.path}](#{metadata.path.replace('/', '').replace('.', '')})\n"
            )
        f.write("\n")

        # Write files
        for metadata, content in processed_files:
            f.write(f"## {metadata.path}\n\n")
            f.write(f"**Size:** {self._format_size(metadata.size)}  \n")
            f.write(
                f"**Modified:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metadata.mtime))}  \n"
            )
            f.write(f"**Encoding:** {metadata.encoding}  \n")
            f.write(f"**Binary:** {'Yes' if metadata.is_binary else 'No'}  \n\n")

            if metadata.is_binary:
                content_str = content.decode("ascii")
                fence = self._get_safe_fence(content_str)
                f.write(f"{fence}\n")
                f.write(content_str)
                f.write(f"\n{fence}\n\n")
            else:
                # Detect language for syntax highlighting
                lang = self._detect_language(metadata.path)
                content_str = content.decode("utf-8")
                fence = self._get_safe_fence(content_str)
                f.write(f"{fence}{lang}\n")
                f.write(content_str)
                f.write(f"\n{fence}\n\n")

    async def _write_yaml_format(
        self, f, source_path: Path, processed_files: List[Tuple[FileMetadata, bytes]]
    ):
        """Write archive in YAML format"""
        # Write header
        f.write("# Combined Files Archive\n")
        f.write(f"version: {__version__}\n")
        f.write(f"created: '{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}'\n")
        f.write(f"source: '{source_path}'\n")
        f.write(f"total_files: {len(processed_files)}\n")
        f.write(f"total_size: {self.stats['bytes_processed']}\n\n")
        f.write("files:\n")

        for metadata, content in processed_files:
            f.write(f"  - path: '{metadata.path}'\n")
            f.write(f"    size: {metadata.size}\n")
            f.write(f"    mtime: {metadata.mtime}\n")
            f.write(f"    encoding: '{metadata.encoding}'\n")
            f.write(f"    is_binary: {str(metadata.is_binary).lower()}\n")

            if metadata.is_binary:
                content_str = content.decode("ascii")
            else:
                content_str = content.decode("utf-8")

            # Escape and format content for YAML
            content_lines = content_str.split("\n")
            f.write("    content: |\n")
            for line in content_lines:
                f.write(f"      {line}\n")
            f.write("\n")

    def _detect_input_format(self, input_path: Path) -> str:
        """
        Detect the format of an archive file for parsing.

        Uses file extension and content inspection to determine format.
        """
        suffix = input_path.suffix.lower()

        # Handle compressed files
        if suffix == ".gz":
            # Get the actual format from the inner extension
            stem = input_path.stem
            inner_suffix = Path(stem).suffix.lower()
            suffix = inner_suffix if inner_suffix else suffix

        format_map = {
            ".json": "json",
            ".xml": "xml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".markdown": "markdown",
            ".txt": "txt",
        }

        detected = format_map.get(suffix, "txt")

        # For ambiguous cases, try to inspect content
        if detected == "txt":
            try:
                # Read first few bytes to detect format
                with open(input_path, "rb") as f:
                    magic = f.read(2)
                    # Check for gzip
                    if magic == b"\x1f\x8b":
                        import gzip

                        with gzip.open(input_path, "rt", encoding="utf-8") as gf:
                            first_chars = gf.read(100).strip()
                    else:
                        f.seek(0)
                        first_chars = f.read(100).decode("utf-8", errors="ignore").strip()

                # Detect by content
                if first_chars.startswith("{"):
                    detected = "json"
                elif first_chars.startswith("<?xml") or first_chars.startswith("<file_archive"):
                    detected = "xml"
                elif first_chars.startswith("# Combined Files Archive") and "```" in first_chars:
                    detected = "markdown"
                elif first_chars.startswith("# Combined Files Archive") or (
                    first_chars.startswith("version:") and "files:" in first_chars
                ):
                    detected = "yaml"
            except Exception:
                pass  # Fall back to txt format

        return detected

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension for syntax highlighting"""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".go": "go",
            ".rs": "rust",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".fish": "fish",
            ".ps1": "powershell",
            ".sql": "sql",
            ".html": "html",
            ".xml": "xml",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".ini": "ini",
            ".cfg": "ini",
            ".conf": "ini",
            ".md": "markdown",
            ".rst": "rst",
            ".tex": "latex",
            ".r": "r",
            ".m": "matlab",
            ".pl": "perl",
            ".lua": "lua",
            ".vim": "vim",
            ".dockerfile": "dockerfile",
            ".makefile": "makefile",
        }
        return lang_map.get(ext, "")

    async def split_files(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        progress: bool = True,
    ) -> bool:
        """Split combined archive back to files with comprehensive error handling"""
        try:
            input_path = Path(input_path).resolve()
            output_path = Path(output_path).resolve()

            if not input_path.exists():
                raise FileCombinerError(f"Input file does not exist: {input_path}")

            if not input_path.is_file():
                raise FileCombinerError(f"Input path is not a file: {input_path}")

            # Detect compression
            is_compressed = input_path.suffix == ".gz" or self._is_gzip_file(input_path)

            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)

            # Check write permissions
            if not os.access(output_path, os.W_OK):
                raise FileCombinerError(
                    f"Cannot write to output directory: {output_path}"
                )

            # Detect archive format
            detected_format = self._detect_input_format(input_path)
            self.logger.info(f"Splitting archive: {input_path}")
            self.logger.info(f"Detected format: {detected_format}")
            self.logger.info(f"Output directory: {output_path}")
            if is_compressed:
                self.logger.info("Detected compressed archive")

            try:
                open_func = gzip.open if is_compressed else open
                mode = "rt" if is_compressed else "r"

                with open_func(input_path, mode, encoding="utf-8") as f:
                    # Dispatch to format-specific parser
                    if detected_format == "json":
                        files_restored = await self._parse_json_archive(f, output_path, progress)
                    elif detected_format == "xml":
                        files_restored = await self._parse_xml_archive(f, output_path, progress)
                    elif detected_format == "yaml":
                        files_restored = await self._parse_yaml_archive(f, output_path, progress)
                    elif detected_format == "markdown":
                        files_restored = await self._parse_markdown_archive(f, output_path, progress)
                    else:  # Default to txt format
                        files_restored = await self._parse_and_restore_files(f, output_path, progress)

                self.logger.info(
                    f"Successfully split {files_restored} files to: {output_path}"
                )
                return True

            except (gzip.BadGzipFile, OSError) as e:
                if is_compressed:
                    self.logger.error(f"Error reading compressed file: {e}")
                    self.logger.info("Trying to read as uncompressed...")
                    # Retry as uncompressed
                    with open(input_path, "r", encoding="utf-8") as f:
                        # Dispatch to format-specific parser
                        if detected_format == "json":
                            files_restored = await self._parse_json_archive(f, output_path, progress)
                        elif detected_format == "xml":
                            files_restored = await self._parse_xml_archive(f, output_path, progress)
                        elif detected_format == "yaml":
                            files_restored = await self._parse_yaml_archive(f, output_path, progress)
                        elif detected_format == "markdown":
                            files_restored = await self._parse_markdown_archive(f, output_path, progress)
                        else:
                            files_restored = await self._parse_and_restore_files(f, output_path, progress)
                    self.logger.info(
                        f"Successfully split {files_restored} files (uncompressed)"
                    )
                    return True
                else:
                    raise

        except Exception as e:
            self.logger.error(f"Failed to split files: {e}")
            if self.verbose:
                self.logger.error(traceback.format_exc())
            return False
        finally:
            self._cleanup_temp_files()

    def _is_gzip_file(self, file_path: Path) -> bool:
        """Check if file is gzip compressed by reading magic bytes"""
        try:
            with open(file_path, "rb") as f:
                magic = f.read(2)
                return magic == b"\x1f\x8b"
        except (OSError, PermissionError):
            return False

    async def _parse_and_restore_files(
        self, f, output_path: Path, progress: bool = True
    ) -> int:
        """Parse archive and restore files with proper content handling"""
        current_metadata = None
        current_encoding = None
        current_content = []
        in_content = False
        files_restored = 0

        # First pass to count files for progress
        total_files = 0
        if progress:
            try:
                current_pos = f.tell()
                for line in f:
                    if line.startswith(self.METADATA_PREFIX):
                        total_files += 1
                f.seek(current_pos)  # Reset to beginning
            except (OSError, io.UnsupportedOperation):
                # If we can't seek (e.g., gzip file), skip progress counting
                total_files = 0

        # Setup progress tracking
        progress_bar = None
        task = None
        if progress and total_files > 0:
            if HAS_RICH and self.console:
                progress_bar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    console=self.console,
                )
                progress_bar.start()
                task = progress_bar.add_task("Extracting files", total=total_files)
            elif HAS_TQDM and tqdm:
                pbar = tqdm(total=total_files, desc="Extracting files", unit="files")
            else:
                print(f"Extracting {total_files} files...")

        line_count = 0
        try:
            for line in f:
                line_count += 1
                line = line.rstrip("\n\r")

                # Check for separator
                if line == self.SEPARATOR:
                    # Save previous file if exists
                    if current_metadata and current_content is not None:
                        try:
                            await self._restore_file(
                                output_path,
                                current_metadata,
                                current_encoding,
                                current_content,
                            )
                            files_restored += 1

                            if progress and total_files > 0:
                                if progress_bar and task is not None:
                                    progress_bar.update(task, advance=1)
                                elif HAS_TQDM and tqdm and "pbar" in locals():
                                    pbar.update(1)
                                elif files_restored % 10 == 0:
                                    print(
                                        f"Extracted {files_restored}/{total_files} files...",
                                        end="\r",
                                    )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to restore file {current_metadata.get('path', 'unknown')}: {e}"
                            )

                    # Reset for next file
                    current_metadata = None
                    current_encoding = None
                    current_content = []
                    in_content = False
                    continue

                # Check for metadata
                if line.startswith(self.METADATA_PREFIX):
                    try:
                        metadata_json = line[len(self.METADATA_PREFIX) :].strip()
                        current_metadata = json.loads(metadata_json)
                        in_content = False
                    except json.JSONDecodeError as e:
                        self.logger.warning(
                            f"Invalid metadata on line {line_count}: {e}"
                        )
                    continue

                # Check for encoding
                if line.startswith(self.ENCODING_PREFIX):
                    current_encoding = line[len(self.ENCODING_PREFIX) :].strip()
                    in_content = True
                    continue

                # Skip header comments and empty lines before content
                if not in_content and (line.startswith("#") or not line.strip()):
                    continue

                # Collect content (including empty lines within content)
                if in_content and current_metadata:
                    current_content.append(line)

            # Handle last file
            if current_metadata and current_content is not None:
                try:
                    await self._restore_file(
                        output_path, current_metadata, current_encoding, current_content
                    )
                    files_restored += 1
                    if progress and total_files > 0:
                        if progress_bar and task is not None:
                            progress_bar.update(task, advance=1)
                        elif HAS_TQDM and tqdm and "pbar" in locals():
                            pbar.update(1)
                except Exception as e:
                    self.logger.error(
                        f"Failed to restore final file {current_metadata.get('path', 'unknown')}: {e}"
                    )

        finally:
            if progress:
                if progress_bar:
                    progress_bar.stop()
                elif HAS_TQDM and tqdm and "pbar" in locals():
                    pbar.close()
                elif total_files > 0:
                    print(f"\nExtracted {files_restored} files")

        return files_restored

    async def _parse_json_archive(self, f, output_path: Path, progress: bool = True) -> int:
        """Parse JSON format archive and restore files"""
        files_restored = 0

        try:
            content = f.read()
            data = json.loads(content)

            if "files" not in data:
                self.logger.error("Invalid JSON archive: missing 'files' key")
                return 0

            files_list = data["files"]
            total_files = len(files_list)

            # Setup progress
            progress_bar = None
            task = None
            if progress and total_files > 0:
                if HAS_RICH and self.console:
                    progress_bar = Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        MofNCompleteColumn(),
                        TimeElapsedColumn(),
                        console=self.console,
                    )
                    progress_bar.start()
                    task = progress_bar.add_task("Extracting files", total=total_files)
                elif HAS_TQDM and tqdm:
                    pbar = tqdm(total=total_files, desc="Extracting files", unit="files")
                else:
                    print(f"Extracting {total_files} files...")

            try:
                for file_data in files_list:
                    try:
                        metadata = {
                            "path": file_data.get("path", ""),
                            "is_binary": file_data.get("is_binary", False),
                            "ends_with_newline": file_data.get("ends_with_newline", True),
                            "mode": file_data.get("mode", 0o644),
                            "mtime": file_data.get("mtime", time.time()),
                        }
                        encoding = file_data.get("encoding", "utf-8")
                        content = file_data.get("content", "")

                        # Convert content to lines for _restore_file
                        content_lines = content.split("\n") if content else []

                        await self._restore_file(output_path, metadata, encoding, content_lines)
                        files_restored += 1

                        if progress and total_files > 0:
                            if progress_bar and task is not None:
                                progress_bar.update(task, advance=1)
                            elif HAS_TQDM and tqdm and "pbar" in locals():
                                pbar.update(1)
                            elif files_restored % 10 == 0:
                                print(f"Extracted {files_restored}/{total_files} files...", end="\r")

                    except Exception as e:
                        self.logger.error(f"Failed to restore file {file_data.get('path', 'unknown')}: {e}")

            finally:
                if progress:
                    if progress_bar:
                        progress_bar.stop()
                    elif HAS_TQDM and tqdm and "pbar" in locals():
                        pbar.close()
                    elif total_files > 0:
                        print(f"\nExtracted {files_restored} files")

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON archive: {e}")
            return 0

        return files_restored

    async def _parse_xml_archive(self, f, output_path: Path, progress: bool = True) -> int:
        """Parse XML format archive and restore files"""
        import xml.etree.ElementTree as ET

        files_restored = 0

        try:
            content = f.read()
            root = ET.fromstring(content)

            files_list = root.findall("file")
            total_files = len(files_list)

            # Setup progress
            progress_bar = None
            task = None
            if progress and total_files > 0:
                if HAS_RICH and self.console:
                    progress_bar = Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        MofNCompleteColumn(),
                        TimeElapsedColumn(),
                        console=self.console,
                    )
                    progress_bar.start()
                    task = progress_bar.add_task("Extracting files", total=total_files)
                elif HAS_TQDM and tqdm:
                    pbar = tqdm(total=total_files, desc="Extracting files", unit="files")
                else:
                    print(f"Extracting {total_files} files...")

            try:
                for file_elem in files_list:
                    try:
                        metadata = {
                            "path": file_elem.get("path", ""),
                            "is_binary": file_elem.get("is_binary", "false").lower() == "true",
                            "ends_with_newline": file_elem.get("ends_with_newline", "true").lower() == "true",
                            "mode": int(file_elem.get("mode", "33188")),  # 0o644 in decimal
                            "mtime": float(file_elem.get("mtime", str(time.time()))),
                        }
                        encoding = file_elem.get("encoding", "utf-8")
                        content = file_elem.text or ""

                        # Convert content to lines for _restore_file
                        content_lines = content.split("\n") if content else []

                        await self._restore_file(output_path, metadata, encoding, content_lines)
                        files_restored += 1

                        if progress and total_files > 0:
                            if progress_bar and task is not None:
                                progress_bar.update(task, advance=1)
                            elif HAS_TQDM and tqdm and "pbar" in locals():
                                pbar.update(1)
                            elif files_restored % 10 == 0:
                                print(f"Extracted {files_restored}/{total_files} files...", end="\r")

                    except Exception as e:
                        self.logger.error(f"Failed to restore file {file_elem.get('path', 'unknown')}: {e}")

            finally:
                if progress:
                    if progress_bar:
                        progress_bar.stop()
                    elif HAS_TQDM and tqdm and "pbar" in locals():
                        pbar.close()
                    elif total_files > 0:
                        print(f"\nExtracted {files_restored} files")

        except ET.ParseError as e:
            self.logger.error(f"Invalid XML archive: {e}")
            return 0

        return files_restored

    async def _parse_yaml_archive(self, f, output_path: Path, progress: bool = True) -> int:
        """Parse YAML format archive and restore files (simple parser, no PyYAML required)"""
        files_restored = 0

        try:
            content = f.read()
            lines = content.split("\n")

            # Simple YAML parser for our specific format
            files_list = []
            current_file = None
            in_content = False
            content_lines = []

            for line in lines:
                if line.startswith("  - path:"):
                    # Save previous file
                    if current_file is not None:
                        current_file["content_lines"] = content_lines
                        files_list.append(current_file)
                    # Start new file
                    path_value = line.split(":", 1)[1].strip().strip("'\"")
                    current_file = {"path": path_value}
                    content_lines = []
                    in_content = False
                elif current_file is not None:
                    if line.startswith("    content: |"):
                        in_content = True
                    elif in_content:
                        if line.startswith("      "):
                            content_lines.append(line[6:])  # Remove 6-space indent
                        elif line.strip() == "" and content_lines:
                            content_lines.append("")  # Preserve empty lines in content
                        else:
                            in_content = False
                    elif line.startswith("    size:"):
                        current_file["size"] = int(line.split(":", 1)[1].strip())
                    elif line.startswith("    mtime:"):
                        current_file["mtime"] = float(line.split(":", 1)[1].strip())
                    elif line.startswith("    encoding:"):
                        current_file["encoding"] = line.split(":", 1)[1].strip().strip("'\"")
                    elif line.startswith("    is_binary:"):
                        current_file["is_binary"] = line.split(":", 1)[1].strip().lower() == "true"

            # Don't forget the last file
            if current_file is not None:
                current_file["content_lines"] = content_lines
                files_list.append(current_file)

            total_files = len(files_list)

            # Setup progress
            progress_bar = None
            task = None
            if progress and total_files > 0:
                if HAS_RICH and self.console:
                    progress_bar = Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        MofNCompleteColumn(),
                        TimeElapsedColumn(),
                        console=self.console,
                    )
                    progress_bar.start()
                    task = progress_bar.add_task("Extracting files", total=total_files)
                elif HAS_TQDM and tqdm:
                    pbar = tqdm(total=total_files, desc="Extracting files", unit="files")
                else:
                    print(f"Extracting {total_files} files...")

            try:
                for file_data in files_list:
                    try:
                        metadata = {
                            "path": file_data.get("path", ""),
                            "is_binary": file_data.get("is_binary", False),
                            "ends_with_newline": True,  # YAML format always has trailing newlines
                            "mode": file_data.get("mode", 0o644),
                            "mtime": file_data.get("mtime", time.time()),
                        }
                        encoding = file_data.get("encoding", "utf-8")

                        await self._restore_file(
                            output_path, metadata, encoding, file_data.get("content_lines", [])
                        )
                        files_restored += 1

                        if progress and total_files > 0:
                            if progress_bar and task is not None:
                                progress_bar.update(task, advance=1)
                            elif HAS_TQDM and tqdm and "pbar" in locals():
                                pbar.update(1)
                            elif files_restored % 10 == 0:
                                print(f"Extracted {files_restored}/{total_files} files...", end="\r")

                    except Exception as e:
                        self.logger.error(f"Failed to restore file {file_data.get('path', 'unknown')}: {e}")

            finally:
                if progress:
                    if progress_bar:
                        progress_bar.stop()
                    elif HAS_TQDM and tqdm and "pbar" in locals():
                        pbar.close()
                    elif total_files > 0:
                        print(f"\nExtracted {files_restored} files")

        except Exception as e:
            self.logger.error(f"Error parsing YAML archive: {e}")
            return 0

        return files_restored

    async def _parse_markdown_archive(self, f, output_path: Path, progress: bool = True) -> int:
        """Parse Markdown format archive and restore files"""
        files_restored = 0

        try:
            content = f.read()
            lines = content.split("\n")

            # Parse markdown format
            files_list = []
            current_file = None
            in_code_block = False
            code_fence = None
            content_lines = []
            current_encoding = "utf-8"
            current_is_binary = False

            for line in lines:
                # Detect file header (## path/to/file.ext)
                if line.startswith("## ") and not in_code_block:
                    # Save previous file
                    if current_file is not None:
                        current_file["content_lines"] = content_lines
                        current_file["encoding"] = current_encoding
                        current_file["is_binary"] = current_is_binary
                        files_list.append(current_file)

                    # Start new file
                    file_path = line[3:].strip()
                    # Skip table of contents section
                    if file_path == "Table of Contents":
                        current_file = None
                        continue
                    current_file = {"path": file_path}
                    content_lines = []
                    in_code_block = False
                    code_fence = None
                    current_encoding = "utf-8"
                    current_is_binary = False
                elif current_file is not None:
                    # Parse metadata
                    if line.startswith("**Encoding:**"):
                        enc = line.split(":", 1)[1].strip().rstrip("  ")
                        current_encoding = enc if enc else "utf-8"
                    elif line.startswith("**Binary:**"):
                        current_is_binary = "Yes" in line

                    # Detect code fence start
                    if not in_code_block and line.startswith("```"):
                        in_code_block = True
                        code_fence = line.rstrip()
                        # Extract just the backticks part for matching
                        fence_match = ""
                        for c in code_fence:
                            if c == "`":
                                fence_match += c
                            else:
                                break
                        code_fence = fence_match
                        continue

                    # Detect code fence end
                    if in_code_block and line.rstrip() == code_fence:
                        in_code_block = False
                        code_fence = None
                        continue

                    # Collect content within code block
                    if in_code_block:
                        content_lines.append(line)

            # Don't forget the last file
            if current_file is not None:
                current_file["content_lines"] = content_lines
                current_file["encoding"] = current_encoding
                current_file["is_binary"] = current_is_binary
                files_list.append(current_file)

            total_files = len(files_list)

            # Setup progress
            progress_bar = None
            task = None
            if progress and total_files > 0:
                if HAS_RICH and self.console:
                    progress_bar = Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        MofNCompleteColumn(),
                        TimeElapsedColumn(),
                        console=self.console,
                    )
                    progress_bar.start()
                    task = progress_bar.add_task("Extracting files", total=total_files)
                elif HAS_TQDM and tqdm:
                    pbar = tqdm(total=total_files, desc="Extracting files", unit="files")
                else:
                    print(f"Extracting {total_files} files...")

            try:
                for file_data in files_list:
                    try:
                        metadata = {
                            "path": file_data.get("path", ""),
                            "is_binary": file_data.get("is_binary", False),
                            "ends_with_newline": True,
                            "mode": 0o644,
                            "mtime": time.time(),
                        }
                        encoding = file_data.get("encoding", "utf-8")

                        await self._restore_file(
                            output_path, metadata, encoding, file_data.get("content_lines", [])
                        )
                        files_restored += 1

                        if progress and total_files > 0:
                            if progress_bar and task is not None:
                                progress_bar.update(task, advance=1)
                            elif HAS_TQDM and tqdm and "pbar" in locals():
                                pbar.update(1)
                            elif files_restored % 10 == 0:
                                print(f"Extracted {files_restored}/{total_files} files...", end="\r")

                    except Exception as e:
                        self.logger.error(f"Failed to restore file {file_data.get('path', 'unknown')}: {e}")

            finally:
                if progress:
                    if progress_bar:
                        progress_bar.stop()
                    elif HAS_TQDM and tqdm and "pbar" in locals():
                        pbar.close()
                    elif total_files > 0:
                        print(f"\nExtracted {files_restored} files")

        except Exception as e:
            self.logger.error(f"Error parsing Markdown archive: {e}")
            return 0

        return files_restored

    def _restore_file_sync(
        self, output_path: Path, metadata: dict, encoding: str, content_lines: List[str]
    ):
        """Synchronous file restoration (runs in thread pool for async)"""
        # SECURITY: Sanitize path to prevent path traversal attacks
        file_path = self._sanitize_path(output_path, metadata["path"])

        # Ensure parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Reconstruct content properly
        if not content_lines:
            content = ""
        else:
            # Join lines with newlines (preserving original line breaks)
            content = "\n".join(content_lines)

            # Handle trailing newline based on original file
            ends_with_newline = metadata.get(
                "ends_with_newline", True
            )  # Default to True for backward compatibility
            if ends_with_newline and not content.endswith("\n"):
                content += "\n"
            elif not ends_with_newline and content.endswith("\n"):
                content = content.rstrip("\n")

        # Write file based on encoding
        if encoding == "base64" or metadata.get("is_binary", False):
            # Decode base64 content
            binary_content = base64.b64decode(content)
            with open(file_path, "wb") as f:
                f.write(binary_content)
        else:
            # Write text content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

        # Restore file metadata if requested
        if self.preserve_permissions and "mode" in metadata and "mtime" in metadata:
            try:
                os.chmod(file_path, metadata["mode"])
                os.utime(file_path, (metadata["mtime"], metadata["mtime"]))
            except (OSError, PermissionError) as e:
                if self.verbose:
                    self.logger.warning(
                        f"Cannot restore metadata for {metadata['path']}: {e}"
                    )

    async def _restore_file(
        self, output_path: Path, metadata: dict, encoding: str, content_lines: List[str]
    ):
        """Restore individual file with proper content reconstruction (async via thread pool)"""
        try:
            await run_in_thread(
                self._restore_file_sync, output_path, metadata, encoding, content_lines
            )
            if self.verbose:
                self.logger.debug(f"Restored: {metadata['path']}")
        except (base64.binascii.Error, ValueError) as e:
            self.logger.error(
                f"Invalid base64 content for {metadata['path']}: {e}"
            )
        except Exception as e:
            self.logger.error(
                f"Error restoring file {metadata.get('path', 'unknown')}: {e}"
            )
            raise

    def _sanitize_path(self, base_dir: Path, unsafe_relative_path: str) -> Path:
        """
        Sanitize and validate extraction path to prevent path traversal attacks.

        This prevents malicious archives from writing files outside the output directory
        via paths like "../../../etc/passwd" or absolute paths.

        Args:
            base_dir: The base output directory (must be absolute)
            unsafe_relative_path: The potentially malicious relative path from archive

        Returns:
            Safe absolute path within base_dir

        Raises:
            SecurityError: If the path would escape the base directory
        """
        # Resolve base_dir to absolute path
        base_dir = base_dir.resolve()

        # Normalize the unsafe path: remove leading slashes, handle backslashes
        normalized_path = unsafe_relative_path.replace("\\", "/")
        normalized_path = normalized_path.lstrip("/")

        # Remove any null bytes (potential injection)
        if "\x00" in normalized_path:
            raise SecurityError(
                f"Path contains null bytes (potential injection): {repr(unsafe_relative_path)}"
            )

        # Construct the target path and resolve it
        target_path = (base_dir / normalized_path).resolve()

        # Verify the resolved path is within base_dir
        try:
            target_path.relative_to(base_dir)
        except ValueError:
            raise SecurityError(
                f"Path traversal attempt detected: '{unsafe_relative_path}' "
                f"would escape output directory '{base_dir}'"
            )

        return target_path

    def _get_safe_fence(self, content: str, base_fence: str = "```") -> str:
        """
        Calculate a safe code fence that won't be broken by content.

        If content contains backtick sequences, returns a longer fence.
        For example, if content has ``` inside, returns ```` instead.

        Args:
            content: The content to be wrapped in code fence
            base_fence: The base fence string (default: ```)

        Returns:
            A fence string that is safe to use with this content
        """
        fence = base_fence
        backtick_char = "`"

        # Find the longest sequence of backticks in content
        max_backticks = 0
        current_count = 0

        for char in content:
            if char == backtick_char:
                current_count += 1
                max_backticks = max(max_backticks, current_count)
            else:
                current_count = 0

        # If content has backtick sequences >= our fence, make fence longer
        if max_backticks >= len(fence):
            fence = backtick_char * (max_backticks + 1)

        return fence

    def _cleanup_temp_files(self):
        """Clean up any temporary files and directories"""
        for temp_item in self._temp_files[:]:
            try:
                temp_path = Path(temp_item)
                if temp_path.exists():
                    if temp_path.is_dir():
                        shutil.rmtree(temp_path)
                    else:
                        temp_path.unlink()
                self._temp_files.remove(temp_item)
            except (OSError, PermissionError):
                pass

    def __del__(self):
        """Destructor to ensure cleanup"""
        if hasattr(self, "_temp_files"):
            self._cleanup_temp_files()


def create_config_file(config_path: Path) -> bool:
    """Create a default configuration file"""
    default_config = """# File Combiner Configuration
# Uncomment and modify values as needed

# Maximum file size to include (e.g., "10M", "500K", "1G")
# max_file_size = "50M"

# Maximum number of worker threads for parallel processing
# max_workers = 8

# Maximum directory depth to traverse
# max_depth = 50

# Compression level for gzip (1-9, higher = better compression but slower)
# compression_level = 6

# Additional patterns to exclude (glob-style patterns)
# exclude_patterns = [
#     "*.backup",
#     "temp/**/*",
#     "*.old"
# ]

# Patterns to include (if specified, only matching files are included)
# include_patterns = [
#     "*.py",
#     "*.js",
#     "*.md"
# ]

# Feature flags
# calculate_checksums = false
# preserve_permissions = false
# follow_symlinks = false
# ignore_binary = false
# verbose = false

# Buffer size for file I/O operations (in bytes)
# buffer_size = 65536
"""

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            f.write(default_config)
        return True
    except (OSError, PermissionError) as e:
        print(f"Error creating config file: {e}")
        return False


def load_config_file(config_path: Path) -> Dict:
    """Load configuration from file with error handling"""
    if not config_path.exists():
        return {}

    config = {}
    try:
        with open(config_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")

                    # Parse different value types
                    if value.lower() in ("true", "false"):
                        config[key] = value.lower() == "true"
                    elif value.isdigit():
                        config[key] = int(value)
                    elif value.startswith("[") and value.endswith("]"):
                        # Simple list parsing
                        items = [
                            item.strip().strip("\"'") for item in value[1:-1].split(",")
                        ]
                        config[key] = [item for item in items if item]
                    else:
                        config[key] = value

    except Exception as e:
        print(f"Warning: Error loading config file on line {line_num}: {e}")

    return config


async def main():
    """Main entry point with comprehensive error handling"""
    parser = argparse.ArgumentParser(
        description="High-performance file combiner for large repositories and AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s combine . combined_files.txt
  %(prog)s split combined_files.txt ./restored

  # GitHub repository support
  %(prog)s combine https://github.com/user/repo repo.txt

  # With compression and verbose output
  %(prog)s combine /path/to/repo combined.txt.gz -cv

  # INCLUDE/EXCLUDE PATTERNS - supports both paths and glob patterns:

  # Include specific directories (full paths or relative to source)
  %(prog)s combine /repo output.txt --include /repo/src --include /repo/docs

  # Include using glob patterns
  %(prog)s combine . output.txt --include "*.py" --include "*.js"

  # Include all Python files anywhere in the project
  %(prog)s combine . output.txt --include "**/*.py"

  # Include specific directory and root markdown files
  %(prog)s combine . output.txt --include ./src --include "*.md"

  # Exclude directories by path
  %(prog)s combine . output.txt --exclude ./node_modules --exclude ./dist

  # Exclude using glob patterns
  %(prog)s combine . output.txt --exclude "*.log" --exclude "__pycache__/**"

  # Combine include and exclude (include src/ but exclude tests within it)
  %(prog)s combine . output.txt --include ./src --exclude "**/test_*"

  # Dry run to preview what will be included
  %(prog)s combine . output.txt --dry-run --verbose --include ./src
        """,
    )

    parser.add_argument(
        "operation", help="Operation to perform (combine or split)"
    )
    parser.add_argument("input_path", help="Input directory, file, or GitHub URL")
    parser.add_argument("output_path", help="Output file or directory")

    # Basic options
    parser.add_argument(
        "-c", "--compress", action="store_true", help="Enable compression"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="Show what would be done"
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Overwrite existing files"
    )

    # Filtering options
    parser.add_argument(
        "-e", "--exclude", action="append", default=[],
        help="Exclude pattern or path. Can be a directory path (./node_modules), "
             "a file path (./secret.txt), or a glob pattern (*.log, **/*.tmp). "
             "Paths are auto-converted to relative patterns. Can be used multiple times."
    )
    parser.add_argument(
        "-i", "--include", action="append", default=[],
        help="Include only matching files. Can be a directory path (./src), "
             "a file path (./README.md), or a glob pattern (*.py, **/*.js). "
             "Paths are auto-converted to relative patterns. Can be used multiple times."
    )
    parser.add_argument("-s", "--max-size", default="50M", help="Maximum file size")
    parser.add_argument("-d", "--max-depth", type=int, default=50, help="Maximum depth")

    # Advanced options
    parser.add_argument(
        "-j", "--jobs", type=int, default=os.cpu_count(), help="Worker threads"
    )
    parser.add_argument(
        "-p", "--preserve-permissions", action="store_true", help="Preserve permissions"
    )
    parser.add_argument(
        "-L", "--follow-symlinks", action="store_true", help="Follow symlinks"
    )
    parser.add_argument(
        "--ignore-binary", action="store_true", help="Skip binary files"
    )
    parser.add_argument("--checksum", action="store_true", help="Calculate checksums")
    parser.add_argument(
        "--compression-level",
        type=int,
        default=6,
        choices=range(1, 10),
        help="Compression level",
    )
    parser.add_argument(
        "--format",
        choices=["txt", "xml", "json", "markdown", "yaml"],
        default=None,
        help="Output format (txt, xml, json, markdown, yaml). Auto-detected from file extension if not specified.",
    )
    parser.add_argument(
        "--no-progress", action="store_true", help="Disable progress bars"
    )
    parser.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Ignore .gitignore patterns (include all files that would normally be gitignored)",
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".config" / "file-combiner" / "config",
        help="Configuration file path",
    )
    parser.add_argument(
        "--create-config", action="store_true", help="Create default config"
    )

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    # Fuzzy command matching for typos
    valid_operations = ["combine", "split"]
    if args.operation not in valid_operations:
        close_matches = difflib.get_close_matches(
            args.operation, valid_operations, n=1, cutoff=0.6
        )
        if close_matches:
            print(
                f"Unknown command '{args.operation}'. Did you mean '{close_matches[0]}'?",
                file=sys.stderr,
            )
            print(f"Usage: file-combiner {close_matches[0]} <input> <output>", file=sys.stderr)
        else:
            print(
                f"Unknown command '{args.operation}'. Valid commands: {', '.join(valid_operations)}",
                file=sys.stderr,
            )
        return 1

    try:
        # Handle config creation
        if args.create_config:
            if create_config_file(args.config):
                print(f"Created default configuration file: {args.config}")
            else:
                print(f"Failed to create configuration file: {args.config}")
                return 1
            return 0

        # Validate required arguments
        if (
            not hasattr(args, "operation")
            or not args.input_path
            or not args.output_path
        ):
            parser.error("operation, input_path, and output_path are required")

        # Load configuration
        config = load_config_file(args.config)

        # Override config with command line arguments
        config.update(
            {
                "max_file_size": args.max_size,
                "max_workers": args.jobs,
                "max_depth": args.max_depth,
                "compression_level": args.compression_level,
                "exclude_patterns": args.exclude,
                "include_patterns": args.include,
                "calculate_checksums": args.checksum,
                "preserve_permissions": args.preserve_permissions,
                "follow_symlinks": args.follow_symlinks,
                "ignore_binary": args.ignore_binary,
                "dry_run": args.dry_run,
                "verbose": args.verbose,
                "respect_gitignore": not args.no_gitignore,
            }
        )

        # Handle progress bar options
        progress = not args.no_progress

        # Create combiner and execute
        combiner = FileCombiner(config)

        if args.operation == "combine":
            success = await combiner.combine_files(
                args.input_path,
                args.output_path,
                compress=args.compress,
                progress=progress,
                format_type=args.format,
            )
        elif args.operation == "split":
            success = await combiner.split_files(
                args.input_path, args.output_path, progress=progress
            )
        else:
            parser.error(f"Unknown operation: {args.operation}")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except FileCombinerError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose if "args" in locals() else False:
            traceback.print_exc()
        return 1


def cli_main():
    """Synchronous entry point for console scripts"""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(cli_main())
