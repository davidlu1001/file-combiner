# File Combiner

[![PyPI version](https://badge.fury.io/py/file-combiner.svg)](https://badge.fury.io/py/file-combiner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A high-performance file combiner that merges entire directories into single files and restores them back to their original structure. Features **multi-format output** (TXT, XML, JSON, Markdown, YAML) with intelligent auto-detection. Optimized for AI agents (Claude, ChatGPT, Copilot) and perfect for large codebases.

## ✨ Features

- 🎨 **Multi-Format Output**: TXT, XML, JSON, Markdown, YAML with auto-detection
- 🚀 **High Performance**: Parallel processing with async I/O
- 🔄 **Bidirectional**: Combine ↔ Split operations with perfect fidelity
- 🗜️ **Smart Compression**: Optional gzip compression
- 🤖 **AI-Optimized**: Perfect format for AI agents with syntax highlighting
- 📁 **Deep Recursion**: Handles nested directories
- 🔧 **Universal Support**: Text, binary, and Unicode files
- ⚡ **Advanced Filtering**: Powerful include/exclude patterns
- 🌐 **GitHub Integration**: Direct repository cloning and combining
- 📊 **Progress Tracking**: Beautiful progress bars with rich terminal output
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

# Multi-format output with auto-detection
file-combiner combine . project.json    # → JSON format (auto-detected)
file-combiner combine . project.xml     # → XML format (auto-detected)
file-combiner combine . project.md      # → Markdown format (auto-detected)
file-combiner combine . project.yaml    # → YAML format (auto-detected)

# Manual format override
file-combiner combine . report.txt --format markdown  # → Markdown in .txt file

# Combine a GitHub repository directly
file-combiner combine https://github.com/davidlu1001/file-combiner repo-archive.txt \
  --exclude "__pycache__/**" --exclude ".git/**"

# Combine with compression (works with all formats)
file-combiner combine /path/to/repo combined.json.gz --compress \
  --exclude "__pycache__/**" --exclude "*.pyc"

# Split archive back to original structure
file-combiner split combined.txt.gz ./restored-project

# Dry run to preview what would be combined
file-combiner combine . output.txt --dry-run --verbose \
  --exclude "__pycache__/**" --exclude "__pypackages__/**"
```

## 📖 Advanced Examples

### GitHub Repository Support

```bash
# Combine any public GitHub repository directly
file-combiner combine https://github.com/user/repo combined-repo.txt

# With smart exclusions for clean output
file-combiner combine https://github.com/davidlu1001/file-combiner repo.txt \
  --exclude "__pycache__/**" --exclude ".git/**" \
  --exclude "*.pyc" --exclude ".pytest_cache/**" \
  --exclude "__pypackages__/**" --exclude ".pdm-build/**"

# Compress large repositories
file-combiner combine https://github.com/user/large-repo repo.txt.gz --compress
```

**Requirements for GitHub support:**
- Git must be installed and available in PATH
- Repository must be publicly accessible (or you must have access)
- Temporary directory space for cloning

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

## 🎨 Multi-Format Output

File-combiner supports 5 output formats, each optimized for different use cases:

### 📄 **TXT Format** (Default)
Traditional plain text format with enhanced headers and metadata.
```bash
file-combiner combine . output.txt
# Auto-detected from .txt extension
```

### 🏷️ **XML Format**
Structured XML with metadata attributes, perfect for enterprise workflows.
```bash
file-combiner combine . output.xml
# Auto-detected from .xml extension
```

### 📋 **JSON Format**
Structured JSON ideal for APIs and programmatic processing.
```bash
file-combiner combine . output.json
# Auto-detected from .json extension
```

### 📝 **Markdown Format**
Beautiful formatted output with syntax highlighting and table of contents.
```bash
file-combiner combine . output.md
# Auto-detected from .md/.markdown extension
```

### ⚙️ **YAML Format**
Human-readable configuration-style format.
```bash
file-combiner combine . output.yaml
# Auto-detected from .yaml/.yml extension
```

### 🎯 **Format Selection**

**Auto-Detection** (Recommended):
```bash
file-combiner combine . project.json    # → JSON format
file-combiner combine . project.xml     # → XML format
file-combiner combine . project.md      # → Markdown format
```

**Manual Override**:
```bash
file-combiner combine . data.txt --format json     # JSON in .txt file
file-combiner combine . report.xml --format markdown  # Markdown in .xml file
```

**With Compression** (All formats supported):
```bash
file-combiner combine . archive.json.gz --compress
file-combiner combine . docs.md.gz --format markdown --compress
```

### 🎨 **Format Comparison**

| Format       | Best For                              | Features                   | Size   |
| ------------ | ------------------------------------- | -------------------------- | ------ |
| **TXT**      | Traditional workflows, simple sharing | Enhanced headers, metadata | Medium |
| **XML**      | Enterprise, structured data           | Attributes, validation     | Large  |
| **JSON**     | APIs, data processing                 | Structured, parseable      | Medium |
| **Markdown** | Documentation, AI training            | Syntax highlighting, TOC   | Medium |
| **YAML**     | Configuration, human-readable         | Clean format, hierarchical | Small  |

### 🤖 **AI-Optimized Formats**

For AI agents and code analysis:
```bash
# Markdown with syntax highlighting (recommended for AI)
file-combiner combine . ai-training.md --exclude "__pycache__/**"

# JSON for programmatic processing
file-combiner combine . data-analysis.json --exclude "node_modules/**"

# YAML for configuration-style output
file-combiner combine . config-review.yaml --exclude ".git/**"
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

# Demo multi-format output
make multi-format-demo
```

## 🎉 Recent Updates (v2.0.2)

### ✨ New Features
- 🎨 **Multi-Format Output** - TXT, XML, JSON, Markdown, YAML with intelligent auto-detection
- 🎯 **Smart Language Detection** - 40+ programming languages with syntax highlighting
- 📝 **Enhanced Markdown Format** - Table of contents, syntax highlighting, rich metadata
- 🔧 **Format Auto-Detection** - Automatically detects format from file extension
- 🗜️ **Universal Compression** - All formats work seamlessly with gzip compression
- ✅ **GitHub URL support** - Clone and combine repositories directly from GitHub URLs
- ✅ **Rich terminal output** with beautiful colored progress bars and formatting
- ✅ **PDM dependency management** for modern Python project workflow
- ✅ **Smart Python exclusions** - Automatically exclude `__pycache__`, `__pypackages__`, etc.
- ✅ Enhanced UI with spinners, colored checkmarks, and time tracking

### 🐛 Bug Fixes
- ✅ Fixed negative `max_workers` validation causing crashes
- ✅ Fixed `_temp_files` initialization issues in constructor
- ✅ Fixed content parsing for files starting with `#` characters
- ✅ Fixed missing `io` module import for error handling
- ✅ Fixed version mismatch between setup.py and file_combiner.py
- ✅ Fixed console script entry point for proper CLI execution

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