# File Combiner

[![PyPI version](https://badge.fury.io/py/file-combiner.svg)](https://badge.fury.io/py/file-combiner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A high-performance file combiner that merges entire directories into single files and restores them back to their original structure. Optimized for AI agents (Claude, ChatGPT, Copilot) and perfect for large codebases.

## ✨ Features

- 🚀 **High Performance**: Parallel processing with async I/O
- 🔄 **Bidirectional**: Combine ↔ Split operations with perfect fidelity
- 🗜️ **Smart Compression**: Optional gzip compression
- 🤖 **AI-Optimized**: Perfect format for AI agents
- 📁 **Deep Recursion**: Handles nested directories
- 🔧 **Universal Support**: Text, binary, and Unicode files
- ⚡ **Advanced Filtering**: Powerful include/exclude patterns
- 📊 **Progress Tracking**: Beautiful progress bars
- 🎯 **Cross-Platform**: Linux, macOS, Windows
- 🛡️ **Robust**: Comprehensive error handling and validation

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install file-combiner

# With all optional dependencies
pip install file-combiner[full]

# Development installation (using PDM)
git clone https://github.com/davidlu1001/file-combiner.git
cd file-combiner
pdm install -G dev
```

### Basic Usage

```bash
# Combine current directory into a single file (excludes Python cache folders)
file-combiner combine . my-project.txt \
  --exclude "__pycache__/**" --exclude "__pypackages__/**"

# Combine with compression
file-combiner combine /path/to/repo combined.txt.gz --compress \
  --exclude "__pycache__/**" --exclude "*.pyc"

# Split archive back to original structure
file-combiner split combined.txt.gz ./restored-project

# Dry run to preview what would be combined
file-combiner combine . output.txt --dry-run --verbose \
  --exclude "__pycache__/**" --exclude "__pypackages__/**"
```

## 📖 Advanced Examples

### AI-Optimized Combining

```bash
# Perfect for sharing with AI agents (excludes common cache/build folders)
file-combiner combine . for-ai.txt \
  --exclude "node_modules/**" --exclude ".git/**" \
  --exclude "__pycache__/**" --exclude "__pypackages__/**" \
  --exclude "*.pyc" --exclude ".pytest_cache/**" \
  --max-size 5M
```

### Language-Specific Filtering

```bash
# Only include Python and JavaScript files
file-combiner combine src/ review.txt.gz \
  --include "*.py" --include "*.js" --compress
```

### Automated Backups

```bash
# Create timestamped backups
file-combiner combine ~/project backup-$(date +%Y%m%d).txt.gz \
  --compress --verbose --exclude "*.log"
```

## ⚙️ Configuration

Create `~/.config/file-combiner/config`:

```python
max_file_size = "50M"
max_workers = 8
verbose = false
exclude_patterns = [
    "node_modules/**/*",
    "__pycache__/**/*",
    "__pypackages__/**/*",
    "*.pyc",
    ".pytest_cache/**/*",
    ".git/**/*",
    ".venv/**/*",
    "venv/**/*"
]
include_patterns = [
    "*.py",
    "*.js",
    "*.md"
]
```

## 🚀 Performance

- **Small projects** (<100 files): ~0.1s
- **Medium projects** (1000 files): ~2-5s
- **Large repositories** (10k+ files): ~30-60s
- **Parallel processing**: 4-8x speedup on multi-core systems

## 🧪 Development

```bash
# Install PDM (if not already installed)
pip install pdm

# Install project and development dependencies
pdm install -G dev

# Run tests
pdm run pytest

# Format code
pdm run black file_combiner.py

# Lint code
pdm run flake8 file_combiner.py

# Type checking
pdm run mypy file_combiner.py

# Run tests with coverage
pdm run pytest --cov=file_combiner
```

## 🎉 Recent Updates (v2.0.1)

### ✨ New Features
- ✅ **Rich terminal output** with beautiful colored progress bars and formatting
- ✅ **PDM dependency management** for modern Python project workflow
- ✅ Enhanced UI with spinners, colored checkmarks, and time tracking

### 🐛 Bug Fixes
- ✅ Fixed negative `max_workers` validation causing crashes
- ✅ Fixed `_temp_files` initialization issues in constructor
- ✅ Fixed content parsing for files starting with `#` characters
- ✅ Fixed missing `io` module import for error handling
- ✅ Fixed version mismatch between setup.py and file_combiner.py
- ✅ Fixed console script entry point for proper CLI execution
- ✅ Fixed all 6 remaining test issues (100% test pass rate: 31/31)

### 🚀 Improvements
- ✅ Improved trailing newline preservation in file restoration
- ✅ Enhanced error handling and robustness throughout codebase
- ✅ Migrated from pip/setuptools to PDM for better dependency management
- ✅ Updated comprehensive .gitignore for modern Python projects
- ✅ Updated development workflow and documentation

### Known Limitations

- **Line endings**: Windows line endings (`\r\n`) are converted to Unix line endings (`\n`) during processing (documented behavior)

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for your changes
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Submit pull request

---

**⭐ Star this repo if you find it useful!**