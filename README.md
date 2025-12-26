# File Combiner

[![PyPI version](https://badge.fury.io/py/file-combiner.svg)](https://badge.fury.io/py/file-combiner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A high-performance file combiner that merges entire directories into single files and restores them back to their original structure. Features **multi-format output** (TXT, XML, JSON, Markdown, YAML) with intelligent auto-detection. Optimized for AI agents (Claude, ChatGPT, Copilot) and perfect for large codebases.

## Features

- **Multi-Format Output**: TXT, XML, JSON, Markdown, YAML with auto-detection
- **Multi-Format Split**: Restore from any format (symmetric combine/split)
- **High Performance**: Parallel processing with async I/O
- **Bidirectional**: Combine and Split operations with perfect fidelity
- **Smart Compression**: Optional gzip compression
- **AI-Optimized**: Perfect format for AI agents with syntax highlighting
- **Gitignore Aware**: Automatically respects `.gitignore` patterns
- **Security Hardened**: Path traversal protection, null byte injection prevention
- **Deep Recursion**: Handles nested directories
- **Universal Support**: Text, binary, and Unicode files
- **Advanced Filtering**: Powerful include/exclude patterns
- **GitHub Integration**: Direct repository cloning and combining
- **Progress Tracking**: Beautiful progress bars with rich terminal output
- **Cross-Platform**: Linux, macOS, Windows
- **Robust**: Comprehensive error handling and graceful signal handling

## Quick Start

### Installation

```bash
# Basic installation
pip install file-combiner

# With all optional dependencies
pip install file-combiner[full]

# Development installation (using uv - recommended)
git clone https://github.com/davidlu1001/file-combiner.git
cd file-combiner
uv sync --all-extras

# Alternative: using pip
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Combine current directory into a single file
# Automatically respects .gitignore patterns
file-combiner combine . my-project.txt

# Multi-format output with auto-detection
file-combiner combine . project.json    # JSON format (auto-detected)
file-combiner combine . project.xml     # XML format (auto-detected)
file-combiner combine . project.md      # Markdown format (auto-detected)
file-combiner combine . project.yaml    # YAML format (auto-detected)

# Split archive back to original structure (works with ALL formats)
file-combiner split combined.json ./restored-project
file-combiner split combined.xml ./restored-project
file-combiner split combined.md ./restored-project

# Manual format override
file-combiner combine . report.txt --format markdown

# Combine a GitHub repository directly
file-combiner combine https://github.com/user/repo repo-archive.txt

# Include files that would normally be gitignored
file-combiner combine . output.txt --no-gitignore

# Combine with compression (works with all formats)
file-combiner combine /path/to/repo combined.json.gz --compress

# Dry run to preview what would be combined
file-combiner combine . output.txt --dry-run --verbose
```

## Advanced Examples

### GitHub Repository Support

```bash
# Combine any public GitHub repository directly
file-combiner combine https://github.com/user/repo combined-repo.txt

# With smart exclusions for clean output
file-combiner combine https://github.com/davidlu1001/file-combiner repo.txt \
  --exclude "__pycache__/**" --exclude ".git/**"

# Compress large repositories
file-combiner combine https://github.com/user/large-repo repo.txt.gz --compress
```

### AI-Optimized Combining

```bash
# Perfect for sharing with AI agents
# Automatically excludes gitignored files
file-combiner combine . for-ai.txt --max-size 5M

# Markdown format with syntax highlighting (recommended for AI)
file-combiner combine . ai-training.md
```

### Language-Specific Filtering

```bash
# Only include Python and JavaScript files
file-combiner combine src/ review.txt.gz \
  --include "*.py" --include "*.js" --compress
```

## Multi-Format Output

File-combiner supports 5 output formats, each optimized for different use cases:

| Format       | Best For                              | Features                   | Size   |
| ------------ | ------------------------------------- | -------------------------- | ------ |
| **TXT**      | Traditional workflows, simple sharing | Enhanced headers, metadata | Medium |
| **XML**      | Enterprise, structured data           | Attributes, validation     | Large  |
| **JSON**     | APIs, data processing                 | Structured, parseable      | Medium |
| **Markdown** | Documentation, AI training            | Syntax highlighting, TOC   | Medium |
| **YAML**     | Configuration, human-readable         | Clean format, hierarchical | Small  |

### Format Selection

**Auto-Detection** (Recommended):
```bash
file-combiner combine . project.json    # JSON format
file-combiner combine . project.xml     # XML format
file-combiner combine . project.md      # Markdown format
```

**Manual Override**:
```bash
file-combiner combine . data.txt --format json
```

## New in v2.1.0

### Security Hardening
- **Path Traversal Protection**: Prevents malicious archives from writing outside target directory
- **Null Byte Injection Prevention**: Blocks path injection attacks
- **Markdown Fence Safety**: Dynamic code fence calculation prevents injection

### Format Symmetry
- **Multi-Format Split**: Restore from JSON, XML, YAML, Markdown (not just TXT)
- **Format Auto-Detection**: Automatically detects archive format for split operations

### Developer Experience
- **Gitignore Awareness**: Automatically respects `.gitignore` patterns
- **Fuzzy Command Matching**: Suggests corrections for typos (`combin` → `combine`)
- **TTY Detection**: Disables progress bars in CI/CD environments
- **Signal Handling**: Graceful cleanup on Ctrl+C

## Configuration

Create `~/.config/file-combiner/config`:

```python
max_file_size = "50M"
max_workers = 8
verbose = false
respect_gitignore = true
exclude_patterns = [
    "node_modules/**/*",
    "__pycache__/**/*",
    ".git/**/*",
    ".venv/**/*"
]
```

## Performance

- **Small projects** (<100 files): ~0.1s
- **Medium projects** (1000 files): ~2-5s
- **Large repositories** (10k+ files): ~30-60s
- **Parallel processing**: 4-8x speedup on multi-core systems

## Development

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/davidlu1001/file-combiner.git
cd file-combiner
uv sync --all-extras

# Run tests
uv run pytest

# Format code (using ruff)
uv run ruff format .

# Lint code (using ruff)
uv run ruff check .

# Type checking
uv run mypy file_combiner.py

# Run tests with coverage
uv run pytest --cov=file_combiner
```

## CLI Reference

```
file-combiner <operation> <input_path> <output_path> [options]

Operations:
  combine    Merge directory into single file
  split      Restore archive to directory structure

Options:
  -c, --compress           Enable gzip compression
  -v, --verbose            Enable verbose output
  -n, --dry-run            Preview without making changes
  --format FORMAT          Output format (txt, xml, json, markdown, yaml)
  --exclude PATTERN        Exclude files matching pattern
  --include PATTERN        Include only files matching pattern
  --max-size SIZE          Maximum file size (e.g., 10M, 1G)
  --no-gitignore           Ignore .gitignore patterns
  --no-progress            Disable progress bars
  --jobs N                 Number of parallel workers
```

## Known Limitations

- **Line endings**: Windows line endings (`\r\n`) are converted to Unix line endings (`\n`) during processing

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for your changes
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Submit pull request

---

**Star this repo if you find it useful!**
