"""Setup script for file-combiner"""
from setuptools import setup
from pathlib import Path
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
setup(
    name="file-combiner",
    version="2.0.0",
    author="File Combiner Project",
    author_email="info@file-combiner.dev",
    description="High-performance file combiner for large repositories and AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/file-combiner",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/file-combiner/issues",
        "Source": "https://github.com/yourusername/file-combiner",
    },
    py_modules=["file_combiner"],
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "progress": ["tqdm>=4.60.0"],
        "dev": ["pytest>=6.0.0", "black>=22.0.0", "flake8>=4.0.0", "pytest-asyncio"],
        "full": ["tqdm>=4.60.0"],
    },
    entry_points={
        "console_scripts": [
            "file-combiner=file_combiner:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Tools",
        "Topic :: System :: Archiving",
    ],
)