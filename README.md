[![PyPI version](https://badge.fury.io/py/file-combiner.svg)](https://badge.fury.io/py/file-combiner)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
A high-performance file combiner that merges entire directories into single files and restores them back to their original structure. Optimized for AI agents (Claude, ChatGPT, Copilot) and perfect for large codebases.
- 🚀 **High Performance**: Parallel processing with async I/O
- 🔄 **Bidirectional**: Combine ↔ Split operations
- 🗜️ **Smart Compression**: Optional gzip compression
- 🤖 **AI-Optimized**: Perfect format for AI agents
- 📁 **Deep Recursion**: Handles nested directories
- 🔧 **Universal Support**: Text, binary, and Unicode files
- ⚡ **Advanced Filtering**: Powerful include/exclude patterns
- 📊 **Progress Tracking**: Beautiful progress bars
- 🎯 **Cross-Platform**: Linux, macOS, Windows
```bash
pip install file-combiner
pip install file-combiner[full]
git clone https://github.com/yourusername/file-combiner.git
cd file-combiner
pip install -e ".[full]"
```
```bash
file-combiner combine . my-project.txt
file-combiner combine /path/to/repo combined.txt.gz --compress
file-combiner split combined.txt.gz ./restored-project
file-combiner combine . output.txt --dry-run --verbose
```
```bash
file-combiner combine . for-ai.txt \
  --exclude "node_modules/**" --exclude ".git/**" \
  --max-size 5M
```
```bash
file-combiner combine src/ review.txt.gz \
  --include "*.py" --include "*.js" --compress
```
```bash
file-combiner combine ~/project backup-$(date +%Y%m%d).txt.gz \
  --compress --verbose --exclude "*.log"
```
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
- **Small projects** (<100 files): ~0.1s
- **Medium projects** (1000 files): ~2-5s  
- **Large repositories** (10k+ files): ~30-60s
- **Parallel processing**: 4-8x speedup on multi-core systems
```bash
pip install -e ".[dev]"
pytest
black file_combiner.py
flake8 file_combiner.py
```
MIT License - see LICENSE file for details.
1. Fork the repository
2. Create feature branch
3. Add tests
4. Submit pull request
---
**⭐ Star this repo if you find it useful!**