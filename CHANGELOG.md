# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2025-01-25

### Added
- **Rich terminal output formatting** with colored progress bars and enhanced UI
- **PDM dependency management** for modern Python project management
- Comprehensive test coverage with all 31 tests passing

### Fixed
- Fixed negative `max_workers` validation causing crashes
- Fixed `_temp_files` initialization issues in constructor
- Fixed content parsing for files starting with `#` characters
- Fixed version mismatch between setup.py and file_combiner.py
- Fixed missing `io` module import for UnsupportedOperation handling
- Fixed console script entry point for proper CLI execution
- Fixed all 6 remaining test issues (dry run, error handling, line endings)

### Improved
- Enhanced trailing newline preservation in file restoration
- Improved error handling and robustness throughout codebase
- Better content reconstruction logic for archive splitting
- More comprehensive validation of configuration parameters
- Beautiful colored terminal output with rich formatting
- Enhanced progress bars with spinners and time tracking

### Changed
- **Migrated from pip/setuptools to PDM** for dependency management
- Removed setup.py and requirements.txt in favor of pyproject.toml
- Updated development workflow to use `pdm install -G dev`

### Updated
- Updated pytest-asyncio requirement to >=0.21.0
- Updated README with PDM installation instructions and examples
- Cleaned up repository structure and removed temporary files

## [2.0.0] - 2024-12-01

### Added
- Complete Python rewrite for better performance
- Async I/O with parallel processing
- Advanced pattern matching with glob support
- Progress bars and detailed statistics
- Comprehensive test suite
- CI/CD with GitHub Actions
- Configuration file support
- Binary file handling with base64 encoding
- Cross-platform compatibility
- Dry run mode for previewing operations
- Better error handling and recovery
- More intuitive command-line interface
- Enhanced AI-friendly output format
- Robust Unicode support

### Changed
- Moved from bash to Python implementation
- New archive format with JSON metadata
- Simplified installation via PyPI
- 10-50x performance improvement over bash version

## [1.0.0] - 2024-01-01

### Added
- Initial bash implementation
- Basic combine and split operations
- Compression support
- Simple exclusion patterns

---
For older versions, see the git history.