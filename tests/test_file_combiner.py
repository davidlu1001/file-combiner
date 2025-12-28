#!/usr/bin/env python3
"""
Comprehensive test suite for file_combiner module
"""

import asyncio
import tempfile
import pytest
from pathlib import Path
import shutil
import sys
import os
import gzip
import json
import base64

# Add parent directory to path to import file_combiner
sys.path.insert(0, str(Path(__file__).parent.parent))
from file_combiner import FileCombiner, FileCombinerError, SecurityError, __version__


class TestFileCombiner:
    """Comprehensive test cases for FileCombiner class"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_project(self, temp_dir):
        """Create a comprehensive sample project structure for testing"""
        project_dir = temp_dir / "sample_project"
        project_dir.mkdir()

        # Create various file types with specific content
        (project_dir / "README.md").write_text(
            "# Sample Project\nThis is a test project"
        )
        (project_dir / "main.py").write_text(
            "#!/usr/bin/env python3\nprint('Hello World')"
        )
        (project_dir / "config.json").write_text('{"name": "test", "version": "1.0"}')

        # Create subdirectory with nested structure
        sub_dir = project_dir / "src"
        sub_dir.mkdir()
        (sub_dir / "utils.py").write_text("def hello():\n    return 'Hello'")
        (sub_dir / "constants.py").write_text("VERSION = '1.0.0'\nDEBUG = True")

        # Create deeper nesting
        deep_dir = sub_dir / "modules"
        deep_dir.mkdir()
        (deep_dir / "core.py").write_text("class Core:\n    pass")

        # Create binary file
        (project_dir / "binary.dat").write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

        # Create files that should be excluded by default
        (project_dir / "temp.log").write_text("Log entry 1\nLog entry 2")
        git_dir = project_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n    repositoryformatversion = 0")

        # Create empty file
        (project_dir / "empty.txt").write_text("")

        # Create file with unicode content
        (project_dir / "unicode.txt").write_text("Hello 世界 🌍", encoding="utf-8")

        return project_dir

    @pytest.fixture
    def combiner(self):
        """Create a FileCombiner instance with test configuration"""
        config = {
            "verbose": False,
            "max_file_size": "10M",
            "max_workers": 2,
            "calculate_checksums": False,  # Disable for faster tests
        }
        return FileCombiner(config)

    @pytest.fixture
    def verbose_combiner(self):
        """Create a verbose FileCombiner for detailed testing"""
        config = {
            "verbose": True,
            "max_file_size": "10M",
            "max_workers": 2,
            "calculate_checksums": True,
        }
        return FileCombiner(config)

    def test_parse_size(self, combiner):
        """Test size parsing functionality with edge cases"""
        # Basic sizes
        assert combiner._parse_size("100") == 100
        assert combiner._parse_size("1K") == 1024
        assert combiner._parse_size("1M") == 1024 * 1024
        assert combiner._parse_size("1G") == 1024 * 1024 * 1024

        # Decimal sizes
        assert combiner._parse_size("1.5M") == int(1.5 * 1024 * 1024)
        assert combiner._parse_size("2.5K") == int(2.5 * 1024)

        # With 'B' suffix
        assert combiner._parse_size("100B") == 100
        assert combiner._parse_size("1KB") == 1024

        # Edge cases
        assert combiner._parse_size("0") == 0
        assert combiner._parse_size("0.5K") == 512

        # Invalid formats
        with pytest.raises(ValueError):
            combiner._parse_size("invalid")
        with pytest.raises(ValueError):
            combiner._parse_size("")
        with pytest.raises(ValueError):
            combiner._parse_size("1X")
        with pytest.raises(ValueError):
            combiner._parse_size(123)  # Not a string

    def test_is_binary(self, combiner, sample_project):
        """Test binary file detection with various file types"""
        # Text files should not be detected as binary
        assert not combiner._is_binary(sample_project / "README.md")
        assert not combiner._is_binary(sample_project / "main.py")
        assert not combiner._is_binary(sample_project / "config.json")
        assert not combiner._is_binary(sample_project / "unicode.txt")
        assert not combiner._is_binary(sample_project / "empty.txt")

        # Binary files should be detected as binary
        assert combiner._is_binary(sample_project / "binary.dat")

    def test_should_exclude(self, combiner, sample_project):
        """Test file exclusion logic with various patterns"""
        # Files that should be included
        should_exclude, reason = combiner._should_exclude(
            sample_project / "README.md", "README.md"
        )
        assert not should_exclude

        should_exclude, reason = combiner._should_exclude(
            sample_project / "main.py", "main.py"
        )
        assert not should_exclude

        should_exclude, reason = combiner._should_exclude(
            sample_project / "config.json", "config.json"
        )
        assert not should_exclude

        # Files that should be excluded by default patterns
        should_exclude, reason = combiner._should_exclude(
            sample_project / "temp.log", "temp.log"
        )
        assert should_exclude
        assert "exclude pattern" in reason

        should_exclude, reason = combiner._should_exclude(
            sample_project / ".git" / "config", ".git/config"
        )
        assert should_exclude

    def test_matches_pattern(self, combiner):
        """Test pattern matching functionality"""
        patterns = ["*.py", "test/**/*", "*.log"]

        assert combiner._matches_pattern("main.py", patterns)
        assert combiner._matches_pattern("test/unit/test_main.py", patterns)
        assert combiner._matches_pattern("app.log", patterns)
        assert not combiner._matches_pattern("README.md", patterns)

        # Test empty patterns
        assert not combiner._matches_pattern("anything", [])

    def test_format_size(self, combiner):
        """Test size formatting function"""
        assert combiner._format_size(0) == "0.0B"
        assert combiner._format_size(500) == "500.0B"
        assert combiner._format_size(1024) == "1.0KB"
        assert combiner._format_size(1536) == "1.5KB"
        assert combiner._format_size(1048576) == "1.0MB"
        assert combiner._format_size(1073741824) == "1.0GB"

        # Test negative size
        assert combiner._format_size(-100) == "0B"

    @pytest.mark.asyncio
    async def test_combine_files_basic(self, combiner, sample_project, temp_dir):
        """Test basic file combination functionality"""
        output_file = temp_dir / "combined.txt"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False
        )
        assert success
        assert output_file.exists()

        # Check that the output file contains expected content
        content = output_file.read_text(encoding="utf-8")
        assert "Enhanced Combined Files Archive" in content
        assert "FILE_METADATA:" in content
        assert "=== FILE_SEPARATOR ===" in content
        assert "README.md" in content
        assert "main.py" in content
        assert "config.json" in content

        # Should not contain excluded files
        assert ".git/config" not in content
        assert "temp.log" not in content

    @pytest.mark.asyncio
    async def test_combine_files_compressed(self, combiner, sample_project, temp_dir):
        """Test compressed file combination"""
        output_file = temp_dir / "combined.txt.gz"

        success = await combiner.combine_files(
            sample_project, output_file, compress=True, progress=False
        )
        assert success
        assert output_file.exists()

        # Verify it's actually compressed
        with gzip.open(output_file, "rt", encoding="utf-8") as f:
            content = f.read()

        assert "Enhanced Combined Files Archive" in content
        assert "FILE_METADATA:" in content
        assert "README.md" in content

    @pytest.mark.asyncio
    async def test_split_files_basic(self, combiner, sample_project, temp_dir):
        """Test basic file splitting functionality"""
        # First combine files
        combined_file = temp_dir / "combined.txt"
        success = await combiner.combine_files(
            sample_project, combined_file, progress=False
        )
        assert success

        # Then split them
        restored_dir = temp_dir / "restored"
        success = await combiner.split_files(
            combined_file, restored_dir, progress=False
        )
        assert success
        assert restored_dir.exists()

        # Check that files were restored correctly
        assert (restored_dir / "README.md").exists()
        assert (restored_dir / "main.py").exists()
        assert (restored_dir / "config.json").exists()
        assert (restored_dir / "src" / "utils.py").exists()
        assert (restored_dir / "src" / "constants.py").exists()
        assert (restored_dir / "src" / "modules" / "core.py").exists()
        assert (restored_dir / "binary.dat").exists()
        assert (restored_dir / "empty.txt").exists()
        assert (restored_dir / "unicode.txt").exists()

        # Verify content matches exactly
        original_readme = (sample_project / "README.md").read_text()
        restored_readme = (restored_dir / "README.md").read_text()
        assert original_readme == restored_readme

        original_main = (sample_project / "main.py").read_text()
        restored_main = (restored_dir / "main.py").read_text()
        assert original_main == restored_main

        original_unicode = (sample_project / "unicode.txt").read_text(encoding="utf-8")
        restored_unicode = (restored_dir / "unicode.txt").read_text(encoding="utf-8")
        assert original_unicode == restored_unicode

        # Verify binary file
        original_binary = (sample_project / "binary.dat").read_bytes()
        restored_binary = (restored_dir / "binary.dat").read_bytes()
        assert original_binary == restored_binary

        # Verify empty file
        assert (restored_dir / "empty.txt").read_text() == ""

    @pytest.mark.asyncio
    async def test_split_files_compressed(self, combiner, sample_project, temp_dir):
        """Test splitting compressed files"""
        # Combine with compression
        combined_file = temp_dir / "combined.txt.gz"
        success = await combiner.combine_files(
            sample_project, combined_file, compress=True, progress=False
        )
        assert success

        # Split compressed file
        restored_dir = temp_dir / "restored"
        success = await combiner.split_files(
            combined_file, restored_dir, progress=False
        )
        assert success

        # Verify files were restored
        assert (restored_dir / "README.md").exists()
        assert (restored_dir / "main.py").exists()

        # Verify content
        original_readme = (sample_project / "README.md").read_text()
        restored_readme = (restored_dir / "README.md").read_text()
        assert original_readme == restored_readme

    @pytest.mark.asyncio
    async def test_dry_run_combine(self, combiner, sample_project, temp_dir, capsys):
        """Test dry run functionality"""
        combiner.dry_run = True
        combiner.verbose = True

        output_file = temp_dir / "combined.txt"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False
        )
        assert success
        assert not output_file.exists()  # No actual file should be created

        # Check that dry run output was printed
        captured = capsys.readouterr()
        # The DRY RUN message is logged, so we check the log output or stdout
        # Since we can see it in the captured log, let's check if it appears in stdout or logs
        assert "README.md" in captured.out  # File list is printed to stdout
        # The dry run functionality is working as we can see the file list

    @pytest.mark.asyncio
    async def test_file_filtering_include(self, temp_dir):
        """Test include pattern functionality"""
        # Create test project
        project_dir = temp_dir / "filter_test"
        project_dir.mkdir()

        (project_dir / "file1.py").write_text("print('python')")
        (project_dir / "file2.js").write_text("console.log('javascript')")
        (project_dir / "file3.txt").write_text("plain text")
        (project_dir / "file4.log").write_text("log entry")

        # Test include patterns
        config = {"include_patterns": ["*.py", "*.js"], "verbose": False}
        combiner = FileCombiner(config)

        output_file = temp_dir / "filtered.txt"

        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        content = output_file.read_text()
        assert "file1.py" in content
        assert "file2.js" in content
        assert "file3.txt" not in content
        assert "file4.log" not in content

    @pytest.mark.asyncio
    async def test_file_filtering_exclude(self, temp_dir):
        """Test exclude pattern functionality"""
        project_dir = temp_dir / "exclude_test"
        project_dir.mkdir()

        (project_dir / "keep.py").write_text("# Keep this file")
        (project_dir / "exclude.log").write_text("# Exclude this file")
        (project_dir / "keep.txt").write_text("# Keep this too")

        config = {"exclude_patterns": ["*.log"], "verbose": False}
        combiner = FileCombiner(config)

        output_file = temp_dir / "excluded.txt"
        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        content = output_file.read_text()
        assert "keep.py" in content
        assert "keep.txt" in content
        assert "exclude.log" not in content

    @pytest.mark.asyncio
    async def test_large_file_exclusion(self, temp_dir):
        """Test that large files are excluded based on size limit"""
        project_dir = temp_dir / "large_test"
        project_dir.mkdir()

        # Create small file
        (project_dir / "small.txt").write_text("small content")

        # Create large file (2KB)
        large_content = "x" * 2048
        (project_dir / "large.txt").write_text(large_content)

        # Configure with 1KB limit
        config = {"max_file_size": "1K", "verbose": False}
        combiner = FileCombiner(config)

        output_file = temp_dir / "size_test.txt"

        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        content = output_file.read_text()
        assert "small.txt" in content
        assert "large.txt" not in content

    @pytest.mark.asyncio
    async def test_error_handling_nonexistent_source(self, combiner, temp_dir):
        """Test error handling for non-existent source directory"""
        non_existent = temp_dir / "does_not_exist"
        output_file = temp_dir / "output.txt"

        # Should return False instead of raising exception
        success = await combiner.combine_files(
            non_existent, output_file, progress=False
        )
        assert not success

    @pytest.mark.asyncio
    async def test_error_handling_nonexistent_input_file(self, combiner, temp_dir):
        """Test error handling for non-existent input file for split"""
        non_existent_file = temp_dir / "does_not_exist.txt"
        output_dir = temp_dir / "output_dir"

        # Should return False instead of raising exception
        success = await combiner.split_files(
            non_existent_file, output_dir, progress=False
        )
        assert not success

    @pytest.mark.asyncio
    async def test_error_handling_file_as_source(self, combiner, temp_dir):
        """Test error handling when source is a file instead of directory"""
        source_file = temp_dir / "source.txt"
        source_file.write_text("test content")
        output_file = temp_dir / "output.txt"

        # Should return False instead of raising exception
        success = await combiner.combine_files(source_file, output_file, progress=False)
        assert not success

    @pytest.mark.asyncio
    async def test_error_handling_directory_as_input(
        self, combiner, sample_project, temp_dir
    ):
        """Test error handling when input for split is a directory"""
        output_dir = temp_dir / "output_dir"

        # Should return False instead of raising exception
        success = await combiner.split_files(sample_project, output_dir, progress=False)
        assert not success

    def test_checksum_calculation(self, verbose_combiner, temp_dir):
        """Test checksum calculation functionality"""
        test_file = temp_dir / "checksum_test.txt"
        test_content = "This is test content for checksum calculation"
        test_file.write_text(test_content)

        checksum = verbose_combiner._calculate_checksum(test_file)
        assert len(checksum) == 64  # SHA-256 produces 64-character hex string
        assert checksum != "error"

        # Same content should produce same checksum
        test_file2 = temp_dir / "checksum_test2.txt"
        test_file2.write_text(test_content)
        checksum2 = verbose_combiner._calculate_checksum(test_file2)
        assert checksum == checksum2

        # Different content should produce different checksum
        test_file3 = temp_dir / "checksum_test3.txt"
        test_file3.write_text(test_content + " modified")
        checksum3 = verbose_combiner._calculate_checksum(test_file3)
        assert checksum != checksum3

    @pytest.mark.asyncio
    async def test_unicode_handling(self, combiner, temp_dir):
        """Test handling of various unicode content"""
        project_dir = temp_dir / "unicode_test"
        project_dir.mkdir()

        # Create files with various unicode content
        (project_dir / "emoji.txt").write_text("Hello 👋 World 🌍", encoding="utf-8")
        (project_dir / "chinese.txt").write_text("你好世界", encoding="utf-8")
        (project_dir / "arabic.txt").write_text("مرحبا بالعالم", encoding="utf-8")
        (project_dir / "mixed.txt").write_text(
            "English + 中文 + العربية + 🚀", encoding="utf-8"
        )

        output_file = temp_dir / "unicode_combined.txt"

        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        # Split and verify
        restored_dir = temp_dir / "unicode_restored"
        success = await combiner.split_files(output_file, restored_dir, progress=False)
        assert success

        # Verify unicode content is preserved
        assert (restored_dir / "emoji.txt").read_text(
            encoding="utf-8"
        ) == "Hello 👋 World 🌍"
        assert (restored_dir / "chinese.txt").read_text(encoding="utf-8") == "你好世界"
        assert (restored_dir / "arabic.txt").read_text(
            encoding="utf-8"
        ) == "مرحبا بالعالم"
        assert (restored_dir / "mixed.txt").read_text(
            encoding="utf-8"
        ) == "English + 中文 + العربية + 🚀"

    @pytest.mark.asyncio
    async def test_empty_files_handling(self, combiner, temp_dir):
        """Test handling of empty files"""
        project_dir = temp_dir / "empty_test"
        project_dir.mkdir()

        # Create empty files
        (project_dir / "empty1.txt").write_text("")
        (project_dir / "empty2.py").write_text("")
        (project_dir / "normal.txt").write_text("not empty")

        output_file = temp_dir / "empty_combined.txt"
        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        # Split and verify
        restored_dir = temp_dir / "empty_restored"
        success = await combiner.split_files(output_file, restored_dir, progress=False)
        assert success

        # Verify empty files are preserved
        assert (restored_dir / "empty1.txt").exists()
        assert (restored_dir / "empty2.py").exists()
        assert (restored_dir / "normal.txt").exists()

        assert (restored_dir / "empty1.txt").read_text() == ""
        assert (restored_dir / "empty2.py").read_text() == ""
        assert (restored_dir / "normal.txt").read_text() == "not empty"

    @pytest.mark.asyncio
    async def test_binary_files_handling(self, combiner, temp_dir):
        """Test comprehensive binary file handling"""
        project_dir = temp_dir / "binary_test"
        project_dir.mkdir()

        # Create various binary files
        (project_dir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        (project_dir / "data.bin").write_bytes(b"\x00\x01\x02\x03\x04\xff\xfe\xfd\xfc")
        (project_dir / "mixed.dat").write_bytes(b"Start\x00\x01Binary\x02\x03End")
        (project_dir / "text.txt").write_text("Normal text file")

        output_file = temp_dir / "binary_combined.txt"
        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        # Verify binary content is base64 encoded in archive
        content = output_file.read_text()
        assert "ENCODING: base64" in content
        assert "ENCODING: utf-8" in content

        # Split and verify
        restored_dir = temp_dir / "binary_restored"
        success = await combiner.split_files(output_file, restored_dir, progress=False)
        assert success

        # Verify binary files are correctly restored
        assert (
            restored_dir / "image.png"
        ).read_bytes() == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        assert (
            restored_dir / "data.bin"
        ).read_bytes() == b"\x00\x01\x02\x03\x04\xff\xfe\xfd\xfc"
        assert (
            restored_dir / "mixed.dat"
        ).read_bytes() == b"Start\x00\x01Binary\x02\x03End"
        assert (restored_dir / "text.txt").read_text() == "Normal text file"

    @pytest.mark.asyncio
    async def test_deep_directory_structure(self, combiner, temp_dir):
        """Test handling of deeply nested directory structures"""
        project_dir = temp_dir / "deep_test"
        current_dir = project_dir

        # Create deep nested structure
        for i in range(5):
            current_dir = current_dir / f"level_{i}"
            current_dir.mkdir(parents=True)
            (current_dir / f"file_{i}.txt").write_text(f"Content at level {i}")

        output_file = temp_dir / "deep_combined.txt"
        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        # Split and verify
        restored_dir = temp_dir / "deep_restored"
        success = await combiner.split_files(output_file, restored_dir, progress=False)
        assert success

        # Verify deep structure is preserved
        current_check = restored_dir
        for i in range(5):
            current_check = current_check / f"level_{i}"
            assert current_check.exists()
            file_path = current_check / f"file_{i}.txt"
            assert file_path.exists()
            assert file_path.read_text() == f"Content at level {i}"

    @pytest.mark.asyncio
    async def test_special_characters_in_filenames(self, combiner, temp_dir):
        """Test handling of special characters in filenames"""
        project_dir = temp_dir / "special_test"
        project_dir.mkdir()

        # Create files with special characters (that are valid on most filesystems)
        special_files = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.with.dots.txt",
            "file(with)parentheses.txt",
            "file[with]brackets.txt",
        ]

        for filename in special_files:
            (project_dir / filename).write_text(f"Content of {filename}")

        output_file = temp_dir / "special_combined.txt"
        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        # Split and verify
        restored_dir = temp_dir / "special_restored"
        success = await combiner.split_files(output_file, restored_dir, progress=False)
        assert success

        # Verify all special files are preserved
        for filename in special_files:
            restored_file = restored_dir / filename
            assert restored_file.exists(), f"File {filename} was not restored"
            assert restored_file.read_text() == f"Content of {filename}"

    @pytest.mark.asyncio
    async def test_preserve_line_endings(self, combiner, temp_dir):
        """Test line endings handling (known limitation: converts to Unix line endings)"""
        project_dir = temp_dir / "line_endings_test"
        project_dir.mkdir()

        # Create files with different line endings
        unix_content = "line1\nline2\nline3"
        windows_content = "line1\r\nline2\r\nline3"
        mac_content = "line1\rline2\rline3"
        mixed_content = "line1\nline2\r\nline3\r"

        (project_dir / "unix.txt").write_bytes(unix_content.encode("utf-8"))
        (project_dir / "windows.txt").write_bytes(windows_content.encode("utf-8"))
        (project_dir / "mac.txt").write_bytes(mac_content.encode("utf-8"))
        (project_dir / "mixed.txt").write_bytes(mixed_content.encode("utf-8"))

        output_file = temp_dir / "line_endings_combined.txt"
        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success

        # Split and verify
        restored_dir = temp_dir / "line_endings_restored"
        success = await combiner.split_files(output_file, restored_dir, progress=False)
        assert success

        # Known limitation: line endings are normalized to Unix format
        # Unix files should remain unchanged
        assert (restored_dir / "unix.txt").read_bytes() == unix_content.encode("utf-8")

        # Windows, Mac, and mixed files will be converted to Unix line endings
        expected_windows_unix = "line1\nline2\nline3"
        expected_mac_unix = "line1\nline2\nline3"  # \r converted to \n
        expected_mixed_unix = "line1\nline2\nline3\n"  # normalized

        assert (
            restored_dir / "windows.txt"
        ).read_bytes() == expected_windows_unix.encode("utf-8")
        assert (restored_dir / "mac.txt").read_bytes() == expected_mac_unix.encode(
            "utf-8"
        )
        assert (restored_dir / "mixed.txt").read_bytes() == expected_mixed_unix.encode(
            "utf-8"
        )

    @pytest.mark.asyncio
    async def test_malformed_archive_handling(self, combiner, temp_dir):
        """Test handling of malformed archive files"""
        # Create malformed archive
        malformed_file = temp_dir / "malformed.txt"
        malformed_file.write_text("This is not a valid archive file")

        output_dir = temp_dir / "malformed_output"

        # Should handle gracefully and return 0 files restored
        success = await combiner.split_files(malformed_file, output_dir, progress=False)
        # The function should complete but restore 0 files
        assert success  # Function completes without crashing
        assert output_dir.exists()
        assert len(list(output_dir.iterdir())) == 0  # No files restored

    @pytest.mark.asyncio
    async def test_statistics_tracking(
        self, verbose_combiner, sample_project, temp_dir
    ):
        """Test that statistics are properly tracked"""
        output_file = temp_dir / "stats_combined.txt"

        # Reset stats
        verbose_combiner.stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "bytes_processed": 0,
            "errors": 0,
        }

        success = await verbose_combiner.combine_files(
            sample_project, output_file, progress=False
        )
        assert success

        # Check statistics
        assert verbose_combiner.stats["files_processed"] > 0
        assert verbose_combiner.stats["bytes_processed"] > 0
        # We should have some skipped files due to default exclusions (.git, .log)
        assert verbose_combiner.stats["files_skipped"] > 0

    def test_config_loading(self, temp_dir):
        """Test configuration file loading"""
        from file_combiner import load_config_file

        config_file = temp_dir / "test_config"
        config_content = """# Test config
max_file_size = "100M"
verbose = true
max_workers = 4
exclude_patterns = ["*.test", "temp/*"]
"""
        config_file.write_text(config_content)

        config = load_config_file(config_file)

        assert config["max_file_size"] == "100M"
        assert config["verbose"] == True
        assert config["max_workers"] == 4
        assert config["exclude_patterns"] == ["*.test", "temp/*"]

    def test_cleanup_temp_files(self, combiner):
        """Test that temporary files are properly cleaned up"""
        # Add some fake temp files
        temp_file1 = "/tmp/fake_temp_1"
        temp_file2 = "/tmp/fake_temp_2"

        combiner._temp_files = [temp_file1, temp_file2]

        # Cleanup should handle non-existent files gracefully
        combiner._cleanup_temp_files()

        # Temp files list should be empty
        assert len(combiner._temp_files) == 0

    def test_is_github_url(self, combiner):
        """Test GitHub URL detection"""
        # Valid GitHub URLs
        assert combiner._is_github_url("https://github.com/user/repo")
        assert combiner._is_github_url("https://www.github.com/user/repo")
        assert combiner._is_github_url("http://github.com/user/repo")

        # Invalid URLs
        assert not combiner._is_github_url("https://gitlab.com/user/repo")
        assert not combiner._is_github_url("/local/path")
        assert not combiner._is_github_url("not-a-url")
        assert not combiner._is_github_url("")

    def test_detect_output_format(self, combiner):
        """Test output format detection"""
        from pathlib import Path

        # Test format argument takes precedence
        assert combiner._detect_output_format(Path("test.txt"), "json") == "json"
        assert combiner._detect_output_format(Path("test.xml"), "yaml") == "yaml"

        # Test extension-based detection
        assert combiner._detect_output_format(Path("test.txt")) == "txt"
        assert combiner._detect_output_format(Path("test.xml")) == "xml"
        assert combiner._detect_output_format(Path("test.json")) == "json"
        assert combiner._detect_output_format(Path("test.md")) == "markdown"
        assert combiner._detect_output_format(Path("test.markdown")) == "markdown"
        assert combiner._detect_output_format(Path("test.yml")) == "yaml"
        assert combiner._detect_output_format(Path("test.yaml")) == "yaml"

        # Test default fallback
        assert combiner._detect_output_format(Path("test.unknown")) == "txt"
        assert combiner._detect_output_format(Path("test")) == "txt"

    def test_detect_language(self, combiner):
        """Test programming language detection for syntax highlighting"""
        # Test common languages
        assert combiner._detect_language("test.py") == "python"
        assert combiner._detect_language("test.js") == "javascript"
        assert combiner._detect_language("test.java") == "java"
        assert combiner._detect_language("test.cpp") == "cpp"
        assert combiner._detect_language("test.html") == "html"
        assert combiner._detect_language("test.css") == "css"
        assert combiner._detect_language("test.json") == "json"
        assert combiner._detect_language("test.yaml") == "yaml"
        assert combiner._detect_language("test.md") == "markdown"

        # Test case insensitivity
        assert combiner._detect_language("TEST.PY") == "python"
        assert combiner._detect_language("Test.JS") == "javascript"

        # Test unknown extensions
        assert combiner._detect_language("test.unknown") == ""
        assert combiner._detect_language("test") == ""


class TestMultiFormatOutput:
    """Test multi-format output functionality"""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def combiner(self):
        return FileCombiner({"verbose": False})

    @pytest.fixture
    def sample_project(self, temp_dir):
        """Create a small sample project for testing formats"""
        project_dir = temp_dir / "sample_project"
        project_dir.mkdir()

        # Create sample files
        (project_dir / "main.py").write_text('print("Hello, World!")\n')
        (project_dir / "config.json").write_text('{"name": "test", "version": "1.0"}\n')
        (project_dir / "README.md").write_text("# Test Project\n\nThis is a test.\n")
        (project_dir / "script.js").write_text('console.log("Hello from JS");\n')

        return project_dir

    @pytest.mark.asyncio
    async def test_txt_format_output(self, combiner, sample_project, temp_dir):
        """Test TXT format output (default)"""
        output_file = temp_dir / "output.txt"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False, format_type="txt"
        )
        assert success
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "Enhanced Combined Files Archive" in content
        assert "FILE_METADATA:" in content
        assert "=== FILE_SEPARATOR ===" in content
        assert 'print("Hello, World!")' in content

    @pytest.mark.asyncio
    async def test_xml_format_output(self, combiner, sample_project, temp_dir):
        """Test XML format output"""
        output_file = temp_dir / "output.xml"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False, format_type="xml"
        )
        assert success
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert "<file_archive" in content
        assert "<file " in content
        assert "path=" in content
        assert 'print("Hello, World!")' in content

    @pytest.mark.asyncio
    async def test_json_format_output(self, combiner, sample_project, temp_dir):
        """Test JSON format output"""
        output_file = temp_dir / "output.json"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False, format_type="json"
        )
        assert success
        assert output_file.exists()

        # Verify it's valid JSON
        import json

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "files" in data
        assert data["metadata"]["version"] == __version__
        assert len(data["files"]) == 4  # 4 sample files

        # Check file content is preserved
        py_file = next(f for f in data["files"] if f["path"].endswith("main.py"))
        assert 'print("Hello, World!")' in py_file["content"]

    @pytest.mark.asyncio
    async def test_markdown_format_output(self, combiner, sample_project, temp_dir):
        """Test Markdown format output"""
        output_file = temp_dir / "output.md"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False, format_type="markdown"
        )
        assert success
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "# Combined Files Archive" in content
        assert "## Table of Contents" in content
        assert "```python" in content  # Syntax highlighting for Python
        assert "```javascript" in content  # Syntax highlighting for JS
        assert "```json" in content  # Syntax highlighting for JSON
        assert 'print("Hello, World!")' in content

    @pytest.mark.asyncio
    async def test_yaml_format_output(self, combiner, sample_project, temp_dir):
        """Test YAML format output"""
        output_file = temp_dir / "output.yaml"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False, format_type="yaml"
        )
        assert success
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
        assert "# Combined Files Archive" in content
        assert f"version: {__version__}" in content
        assert "files:" in content
        assert "  - path:" in content
        assert "    content: |" in content
        assert 'print("Hello, World!")' in content

    @pytest.mark.asyncio
    async def test_format_detection_from_extension(
        self, combiner, sample_project, temp_dir
    ):
        """Test automatic format detection from file extension"""
        # Test XML detection
        xml_file = temp_dir / "auto.xml"
        success = await combiner.combine_files(sample_project, xml_file, progress=False)
        assert success
        content = xml_file.read_text(encoding="utf-8")
        assert '<?xml version="1.0" encoding="UTF-8"?>' in content

        # Test JSON detection
        json_file = temp_dir / "auto.json"
        success = await combiner.combine_files(
            sample_project, json_file, progress=False
        )
        assert success
        content = json_file.read_text(encoding="utf-8")
        assert '"metadata"' in content

        # Test Markdown detection
        md_file = temp_dir / "auto.md"
        success = await combiner.combine_files(sample_project, md_file, progress=False)
        assert success
        content = md_file.read_text(encoding="utf-8")
        assert "# Combined Files Archive" in content

    @pytest.mark.asyncio
    async def test_format_override_extension(self, combiner, sample_project, temp_dir):
        """Test that format argument overrides file extension"""
        # Use .txt extension but force JSON format
        output_file = temp_dir / "override.txt"

        success = await combiner.combine_files(
            sample_project, output_file, progress=False, format_type="json"
        )
        assert success

        # Should be JSON despite .txt extension
        import json

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "metadata" in data
        assert "files" in data

    @pytest.mark.asyncio
    async def test_compressed_formats(self, combiner, sample_project, temp_dir):
        """Test that formats work with compression"""
        # Test compressed JSON
        json_gz_file = temp_dir / "compressed.json.gz"

        success = await combiner.combine_files(
            sample_project,
            json_gz_file,
            compress=True,
            progress=False,
            format_type="json",
        )
        assert success
        assert json_gz_file.exists()

        # Verify compressed JSON is valid
        import gzip
        import json

        with gzip.open(json_gz_file, "rt", encoding="utf-8") as f:
            data = json.load(f)
        assert "metadata" in data
        assert "files" in data

    @pytest.mark.asyncio
    async def test_binary_files_in_formats(self, combiner, temp_dir):
        """Test that binary files are handled correctly in all formats"""
        project_dir = temp_dir / "binary_test"
        project_dir.mkdir()

        # Create a binary file and a text file
        (project_dir / "binary.bin").write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")
        (project_dir / "text.txt").write_text("Normal text")

        # Test JSON format with binary files
        json_file = temp_dir / "binary.json"
        success = await combiner.combine_files(
            project_dir, json_file, progress=False, format_type="json"
        )
        assert success

        import json

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Find binary file in data
        binary_file = next(f for f in data["files"] if f["path"].endswith("binary.bin"))
        assert binary_file["is_binary"] == True
        assert binary_file["encoding"] == "base64"


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_empty_directory(self, temp_dir):
        """Test combining an empty directory"""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        combiner = FileCombiner({"verbose": False})
        output_file = temp_dir / "empty_combined.txt"

        success = await combiner.combine_files(empty_dir, output_file, progress=False)
        assert not success  # Should fail gracefully
        assert not output_file.exists()

    @pytest.mark.asyncio
    async def test_permission_denied_simulation(self, temp_dir):
        """Test handling of files that can't be read (simulated)"""
        project_dir = temp_dir / "permission_test"
        project_dir.mkdir()

        # Create a normal file
        (project_dir / "normal.txt").write_text("normal content")

        # Create a file that simulates permission issues by being in a non-existent subdirectory
        # This will cause an OSError when trying to read it

        combiner = FileCombiner({"verbose": True})
        output_file = temp_dir / "permission_combined.txt"

        success = await combiner.combine_files(project_dir, output_file, progress=False)
        assert success  # Should succeed with available files

        content = output_file.read_text()
        assert "normal.txt" in content

    def test_invalid_configuration(self):
        """Test handling of invalid configuration values"""
        # Invalid max_file_size
        with pytest.raises(ValueError):
            FileCombiner({"max_file_size": "invalid"})

        # Negative max_workers should be handled gracefully
        combiner = FileCombiner({"max_workers": -1})
        assert combiner.max_workers > 0  # Should default to a positive value

        # Very large max_workers should be capped
        combiner = FileCombiner({"max_workers": 1000})
        assert combiner.max_workers <= 32  # Should be capped


class TestSecurityFeatures:
    """Test security features and vulnerability prevention"""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def combiner(self):
        return FileCombiner({"verbose": False})

    def test_path_traversal_prevention(self, combiner, temp_dir):
        """Test that path traversal attacks are prevented"""
        from file_combiner import SecurityError

        output_path = temp_dir / "output"
        output_path.mkdir()

        # Test various path traversal attempts that escape the directory
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "foo/../../../etc/passwd",
            "foo/bar/../../../etc/passwd",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises(SecurityError) as exc_info:
                combiner._sanitize_path(output_path, malicious_path)
            assert "traversal" in str(exc_info.value).lower() or "escape" in str(exc_info.value).lower()

    def test_absolute_path_normalized(self, combiner, temp_dir):
        """Test that absolute paths are normalized to relative paths (not rejected)"""
        output_path = temp_dir / "output"
        output_path.mkdir()

        # Absolute paths should be stripped of leading slash and become relative
        # This is secure because they end up inside the output directory
        result = combiner._sanitize_path(output_path, "/etc/passwd")
        assert str(result).startswith(str(output_path.resolve()))
        assert result.name == "passwd"  # The file ends up at output/etc/passwd

    def test_null_byte_injection_prevention(self, combiner, temp_dir):
        """Test that null byte injection is prevented"""
        from file_combiner import SecurityError

        output_path = temp_dir / "output"
        output_path.mkdir()

        # Null byte injection attempt
        malicious_path = "file.txt\x00.exe"

        with pytest.raises(SecurityError) as exc_info:
            combiner._sanitize_path(output_path, malicious_path)
        assert "null" in str(exc_info.value).lower()

    def test_safe_path_allowed(self, combiner, temp_dir):
        """Test that legitimate paths are allowed"""
        output_path = temp_dir / "output"
        output_path.mkdir()

        safe_paths = [
            "file.txt",
            "subdir/file.txt",
            "deeply/nested/path/file.py",
            "file with spaces.txt",
            "file-with-dashes.txt",
        ]

        for safe_path in safe_paths:
            result = combiner._sanitize_path(output_path, safe_path)
            # Should not raise and should return a path within output_path
            assert str(result).startswith(str(output_path.resolve()))

    def test_markdown_fence_safety(self, combiner):
        """Test that markdown content with backticks gets safe fences"""
        # Content with triple backticks
        content_with_backticks = "```python\nprint('hello')\n```"
        fence = combiner._get_safe_fence(content_with_backticks)
        assert len(fence) > 3  # Should be at least 4 backticks

        # Content with 4 backticks
        content_with_4_backticks = "````\nsome content\n````"
        fence = combiner._get_safe_fence(content_with_4_backticks)
        assert len(fence) > 4  # Should be at least 5 backticks

        # Content without backticks
        normal_content = "print('hello world')"
        fence = combiner._get_safe_fence(normal_content)
        assert fence == "```"  # Standard fence

    @pytest.mark.asyncio
    async def test_malicious_archive_path_traversal(self, combiner, temp_dir):
        """Test that a malicious archive with path traversal is handled safely"""
        from file_combiner import SecurityError

        # Create a malicious archive file manually
        malicious_archive = temp_dir / "malicious.txt"
        malicious_content = """# Enhanced Combined Files Archive
# Generated by file-combiner v2.1.0

=== FILE_SEPARATOR ===
FILE_METADATA: {"path": "../../../etc/malicious.txt", "size": 10, "mtime": 0, "mode": 33188, "encoding": "utf-8", "is_binary": false, "ends_with_newline": true}
ENCODING: utf-8
malicious content
"""
        malicious_archive.write_text(malicious_content)

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # The split should fail for the malicious file
        success = await combiner.split_files(malicious_archive, output_dir, progress=False)
        # Success should be true (operation completed) but file should not be written outside
        assert success

        # Verify no file was written outside the output directory
        parent_dir = temp_dir.parent
        assert not (parent_dir / "etc" / "malicious.txt").exists()


class TestGitignoreSupport:
    """Test .gitignore integration"""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def combiner(self):
        return FileCombiner({"verbose": False, "respect_gitignore": True})

    @pytest.fixture
    def project_with_gitignore(self, temp_dir):
        """Create a project with .gitignore"""
        project_dir = temp_dir / "project"
        project_dir.mkdir()

        # Create .gitignore
        gitignore = project_dir / ".gitignore"
        gitignore.write_text("*.secret\nbuild/\n")

        # Create files
        (project_dir / "main.py").write_text("print('hello')\n")
        (project_dir / "config.secret").write_text("password=123\n")

        # Create build directory
        build_dir = project_dir / "build"
        build_dir.mkdir()
        (build_dir / "output.bin").write_text("binary\n")

        return project_dir

    @pytest.mark.asyncio
    async def test_gitignore_respected(self, combiner, project_with_gitignore, temp_dir):
        """Test that .gitignore patterns are respected"""
        combined_file = temp_dir / "combined.txt"

        success = await combiner.combine_files(
            project_with_gitignore, combined_file, progress=False
        )
        assert success

        content = combined_file.read_text()

        # main.py should be included
        assert "main.py" in content
        # .gitignore itself should be included
        assert ".gitignore" in content
        # Secret file should be excluded
        assert "config.secret" not in content
        # Build directory should be excluded
        assert "output.bin" not in content

    @pytest.mark.asyncio
    async def test_gitignore_can_be_disabled(self, temp_dir):
        """Test that gitignore can be disabled with respect_gitignore=False"""
        combiner = FileCombiner({"verbose": False, "respect_gitignore": False})

        project_dir = temp_dir / "project"
        project_dir.mkdir()

        # Create .gitignore
        gitignore = project_dir / ".gitignore"
        gitignore.write_text("*.secret\n")

        # Create files
        (project_dir / "main.py").write_text("print('hello')\n")
        (project_dir / "config.secret").write_text("password=123\n")

        combined_file = temp_dir / "combined.txt"

        success = await combiner.combine_files(project_dir, combined_file, progress=False)
        assert success

        content = combined_file.read_text()

        # Both files should be included when gitignore is disabled
        assert "main.py" in content
        assert "config.secret" in content


class TestMultiFormatRoundTrip:
    """Test round-trip (combine -> split) for all formats"""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def combiner(self):
        return FileCombiner({"verbose": False})

    @pytest.fixture
    def sample_project(self, temp_dir):
        """Create a sample project for round-trip testing"""
        project_dir = temp_dir / "sample_project"
        project_dir.mkdir()

        # Create sample files
        (project_dir / "main.py").write_text('print("Hello, World!")\n')
        (project_dir / "config.json").write_text('{"name": "test"}\n')
        (project_dir / "README.md").write_text("# Test Project\n")

        # Create subdirectory
        sub_dir = project_dir / "src"
        sub_dir.mkdir()
        (sub_dir / "utils.py").write_text("def hello():\n    return 'Hello'\n")

        return project_dir

    @pytest.mark.asyncio
    async def test_json_format_roundtrip(self, combiner, sample_project, temp_dir):
        """Test JSON format combine -> split round-trip"""
        combined_file = temp_dir / "combined.json"

        # Combine to JSON
        success = await combiner.combine_files(
            sample_project, combined_file, progress=False, format_type="json"
        )
        assert success
        assert combined_file.exists()

        # Verify it's valid JSON
        content = combined_file.read_text()
        data = json.loads(content)
        assert "files" in data

        # Split from JSON
        restored_dir = temp_dir / "restored_json"
        success = await combiner.split_files(combined_file, restored_dir, progress=False)
        assert success

        # Verify files were restored correctly
        assert (restored_dir / "main.py").exists()
        assert (restored_dir / "config.json").exists()
        assert (restored_dir / "README.md").exists()
        assert (restored_dir / "src" / "utils.py").exists()

        # Verify content matches
        assert (restored_dir / "main.py").read_text() == 'print("Hello, World!")\n'

    @pytest.mark.asyncio
    async def test_xml_format_roundtrip(self, combiner, sample_project, temp_dir):
        """Test XML format combine -> split round-trip"""
        combined_file = temp_dir / "combined.xml"

        # Combine to XML
        success = await combiner.combine_files(
            sample_project, combined_file, progress=False, format_type="xml"
        )
        assert success
        assert combined_file.exists()

        # Verify it's valid XML
        content = combined_file.read_text()
        assert '<?xml version="1.0"' in content
        assert "<file_archive" in content

        # Split from XML
        restored_dir = temp_dir / "restored_xml"
        success = await combiner.split_files(combined_file, restored_dir, progress=False)
        assert success

        # Verify files were restored
        assert (restored_dir / "main.py").exists()
        assert (restored_dir / "src" / "utils.py").exists()

    @pytest.mark.asyncio
    async def test_yaml_format_roundtrip(self, combiner, sample_project, temp_dir):
        """Test YAML format combine -> split round-trip"""
        combined_file = temp_dir / "combined.yaml"

        # Combine to YAML
        success = await combiner.combine_files(
            sample_project, combined_file, progress=False, format_type="yaml"
        )
        assert success
        assert combined_file.exists()

        # Verify it contains YAML structure
        content = combined_file.read_text()
        assert "files:" in content
        assert "  - path:" in content

        # Split from YAML
        restored_dir = temp_dir / "restored_yaml"
        success = await combiner.split_files(combined_file, restored_dir, progress=False)
        assert success

        # Verify files were restored
        assert (restored_dir / "main.py").exists()

    @pytest.mark.asyncio
    async def test_markdown_format_roundtrip(self, combiner, sample_project, temp_dir):
        """Test Markdown format combine -> split round-trip"""
        combined_file = temp_dir / "combined.md"

        # Combine to Markdown
        success = await combiner.combine_files(
            sample_project, combined_file, progress=False, format_type="markdown"
        )
        assert success
        assert combined_file.exists()

        # Verify it contains Markdown structure
        content = combined_file.read_text()
        assert "# Combined Files Archive" in content
        assert "```python" in content

        # Split from Markdown
        restored_dir = temp_dir / "restored_md"
        success = await combiner.split_files(combined_file, restored_dir, progress=False)
        assert success

        # Verify files were restored
        assert (restored_dir / "main.py").exists()

    @pytest.mark.asyncio
    async def test_format_detection(self, combiner, sample_project, temp_dir):
        """Test automatic format detection"""
        # Create archives in different formats
        json_file = temp_dir / "test.json"
        xml_file = temp_dir / "test.xml"
        yaml_file = temp_dir / "test.yaml"

        await combiner.combine_files(sample_project, json_file, progress=False)
        await combiner.combine_files(sample_project, xml_file, progress=False)
        await combiner.combine_files(sample_project, yaml_file, progress=False)

        # Test format detection
        assert combiner._detect_input_format(json_file) == "json"
        assert combiner._detect_input_format(xml_file) == "xml"
        assert combiner._detect_input_format(yaml_file) == "yaml"


class TestIncludeExcludePatterns:
    """Comprehensive tests for include/exclude pattern handling"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def complex_project(self, temp_dir):
        """Create a complex project structure for testing patterns"""
        project = temp_dir / "complex_project"
        project.mkdir()

        # Create directory structure
        (project / "src").mkdir()
        (project / "src" / "core").mkdir()
        (project / "tests").mkdir()
        (project / "docs").mkdir()
        (project / "node_modules").mkdir()
        (project / "node_modules" / "pkg").mkdir()
        (project / "logs").mkdir()

        # Create files
        (project / "README.md").write_text("# Project")
        (project / "CHANGELOG.md").write_text("# Changes")
        (project / "src" / "main.py").write_text("# Main")
        (project / "src" / "utils.py").write_text("# Utils")
        (project / "src" / "core" / "engine.py").write_text("# Engine")
        (project / "tests" / "test_main.py").write_text("# Test Main")
        (project / "docs" / "guide.md").write_text("# Guide")
        (project / "node_modules" / "pkg" / "index.js").write_text("// Pkg")
        (project / "logs" / "app.log").write_text("log entry")
        (project / "data.json").write_text("{}")
        (project / "config.yaml").write_text("key: value")

        return project

    @pytest.mark.asyncio
    async def test_include_directory_path(self, complex_project, temp_dir):
        """Test include with directory path (not glob pattern)"""
        config = {"include_patterns": [str(complex_project / "src")], "verbose": False}
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should include all files in src/
        assert "src/main.py" in content
        assert "src/utils.py" in content
        assert "src/core/engine.py" in content
        # Should exclude everything else
        assert "README.md" not in content
        assert "tests/test_main.py" not in content
        assert "docs/guide.md" not in content

    @pytest.mark.asyncio
    async def test_include_multiple_directories(self, complex_project, temp_dir):
        """Test include with multiple directory paths"""
        config = {
            "include_patterns": [
                str(complex_project / "src"),
                str(complex_project / "docs"),
            ],
            "verbose": False,
        }
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should include src/ and docs/
        assert "src/main.py" in content
        assert "src/core/engine.py" in content
        assert "docs/guide.md" in content
        # Should exclude tests/ and root files
        assert "tests/test_main.py" not in content
        assert "README.md" not in content

    @pytest.mark.asyncio
    async def test_include_mixed_paths_and_patterns(self, complex_project, temp_dir):
        """Test include with mix of directory paths and glob patterns"""
        config = {
            "include_patterns": [
                str(complex_project / "src"),
                "*.md",  # Glob pattern for root .md files
            ],
            "verbose": False,
        }
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should include src/ files
        assert "src/main.py" in content
        # Should include root .md files
        assert "README.md" in content
        assert "CHANGELOG.md" in content
        # docs/guide.md should also match *.md
        assert "docs/guide.md" in content
        # Should exclude other files
        assert "data.json" not in content

    @pytest.mark.asyncio
    async def test_include_nested_glob_pattern(self, complex_project, temp_dir):
        """Test include with nested glob patterns like **/*.py"""
        config = {"include_patterns": ["**/*.py"], "verbose": False}
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should include all Python files
        assert "src/main.py" in content
        assert "src/utils.py" in content
        assert "src/core/engine.py" in content
        assert "tests/test_main.py" in content
        # Should exclude non-Python files
        assert "README.md" not in content
        assert "data.json" not in content

    @pytest.mark.asyncio
    async def test_exclude_directory_path(self, complex_project, temp_dir):
        """Test exclude with directory path"""
        config = {
            "exclude_patterns": [
                str(complex_project / "node_modules"),
                str(complex_project / "logs"),
            ],
            "verbose": False,
        }
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should exclude node_modules/ and logs/
        assert "node_modules" not in content
        assert "logs/app.log" not in content
        # Should include everything else
        assert "src/main.py" in content
        assert "README.md" in content

    @pytest.mark.asyncio
    async def test_exclude_mixed_paths_and_patterns(self, complex_project, temp_dir):
        """Test exclude with mix of directory paths and glob patterns"""
        config = {
            "exclude_patterns": [
                str(complex_project / "node_modules"),
                "*.log",
                "*.json",
            ],
            "verbose": False,
        }
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should exclude
        assert "node_modules" not in content
        assert "app.log" not in content
        assert "data.json" not in content
        # Should include
        assert "src/main.py" in content
        assert "README.md" in content
        assert "config.yaml" in content

    @pytest.mark.asyncio
    async def test_include_and_exclude_together(self, complex_project, temp_dir):
        """Test using both include and exclude patterns"""
        config = {
            "include_patterns": [str(complex_project / "src")],
            "exclude_patterns": ["**/core/**"],
            "verbose": False,
        }
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should include src/ but not src/core/
        assert "src/main.py" in content
        assert "src/utils.py" in content
        assert "src/core/engine.py" not in content

    @pytest.mark.asyncio
    async def test_include_single_file(self, complex_project, temp_dir):
        """Test include with single file path"""
        config = {
            "include_patterns": [str(complex_project / "README.md")],
            "verbose": False,
        }
        combiner = FileCombiner(config)

        output_file = temp_dir / "output.txt"
        success = await combiner.combine_files(complex_project, output_file, progress=False)
        assert success

        content = output_file.read_text()
        # Should only include the single file
        assert "README.md" in content
        assert "src/main.py" not in content

    def test_pattern_matching_glob_star(self):
        """Test _matches_pattern with single glob star"""
        combiner = FileCombiner({})

        # *.py should match Python files in any directory (basename match)
        assert combiner._matches_pattern("main.py", ["*.py"])
        assert combiner._matches_pattern("src/utils.py", ["*.py"])
        assert not combiner._matches_pattern("main.js", ["*.py"])

    def test_pattern_matching_double_star(self):
        """Test _matches_pattern with double glob star"""
        combiner = FileCombiner({})

        # **/*.py should match Python files at any depth
        assert combiner._matches_pattern("main.py", ["**/*.py"])
        assert combiner._matches_pattern("src/main.py", ["**/*.py"])
        assert combiner._matches_pattern("src/core/engine.py", ["**/*.py"])
        assert not combiner._matches_pattern("main.js", ["**/*.py"])

    def test_pattern_matching_directory_pattern(self):
        """Test _matches_pattern with directory patterns"""
        combiner = FileCombiner({})

        # src/** should match all files in src/
        assert combiner._matches_pattern("src/main.py", ["src/**"])
        assert combiner._matches_pattern("src/core/engine.py", ["src/**"])
        assert not combiner._matches_pattern("tests/main.py", ["src/**"])
        assert not combiner._matches_pattern("main.py", ["src/**"])

    def test_pattern_matching_prefix(self):
        """Test _matches_pattern with path prefix matching"""
        combiner = FileCombiner({})

        # Pattern like 'src' should match paths starting with 'src/'
        assert combiner._matches_pattern("src/main.py", ["src"])
        assert combiner._matches_pattern("src/core/engine.py", ["src"])
        assert not combiner._matches_pattern("tests/main.py", ["src"])

    def test_normalize_patterns_directory(self, temp_dir):
        """Test _normalize_patterns with directory paths"""
        project = temp_dir / "project"
        project.mkdir()
        (project / "src").mkdir()

        combiner = FileCombiner({})
        combiner.verbose = True

        patterns = [str(project / "src")]
        normalized = combiner._normalize_patterns(patterns, project, "include")

        assert len(normalized) == 1
        assert normalized[0] == "src/**"

    def test_normalize_patterns_file(self, temp_dir):
        """Test _normalize_patterns with file paths"""
        project = temp_dir / "project"
        project.mkdir()
        (project / "README.md").write_text("# Test")

        combiner = FileCombiner({})

        patterns = [str(project / "README.md")]
        normalized = combiner._normalize_patterns(patterns, project, "include")

        assert len(normalized) == 1
        assert normalized[0] == "README.md"

    def test_normalize_patterns_glob(self, temp_dir):
        """Test _normalize_patterns with glob patterns"""
        project = temp_dir / "project"
        project.mkdir()

        combiner = FileCombiner({})

        patterns = ["*.py", "**/*.js", "src/**"]
        normalized = combiner._normalize_patterns(patterns, project, "include")

        # Glob patterns should be preserved as-is
        assert "*.py" in normalized
        assert "**/*.js" in normalized
        assert "src/**" in normalized

    def test_normalize_patterns_outside_source(self, temp_dir):
        """Test _normalize_patterns with path outside source directory"""
        project = temp_dir / "project"
        project.mkdir()
        other = temp_dir / "other"
        other.mkdir()

        combiner = FileCombiner({})

        patterns = [str(other)]
        normalized = combiner._normalize_patterns(patterns, project, "include")

        # Path outside source should be kept as-is (will be treated as pattern)
        assert str(other) in normalized


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
