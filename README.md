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

# Development installation
git clone https://github.com/yourusername/file-combiner.git
cd file-combiner
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Combine current directory into a single file
file-combiner combine . my-project.txt

# Combine with compression
file-combiner combine /path/to/repo combined.txt.gz --compress

# Split archive back to original structure
file-combiner split combined.txt.gz ./restored-project

# Dry run to preview what would be combined
file-combiner combine . output.txt --dry-run --verbose
```

## 📖 Advanced Examples

### AI-Optimized Combining

```bash
# Perfect for sharing with AI agents
file-combiner combine . for-ai.txt \
  --exclude "node_modules/**" --exclude ".git/**" \
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
    "*.pyc",
    ".git/**/*"
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
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black file_combiner.py

# Lint code
flake8 file_combiner.py
```

## 🐛 Recent Bug Fixes (v2.0.1)

- ✅ Fixed negative `max_workers` validation
- ✅ Fixed `_temp_files` initialization issues
- ✅ Fixed content parsing for files starting with `#`
- ✅ Improved trailing newline preservation
- ✅ Enhanced error handling and robustness
- ✅ Updated dependencies and requirements

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