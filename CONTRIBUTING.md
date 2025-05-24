We welcome contributions to the File Combiner project! This document provides guidelines for contributing.
1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/file-combiner.git
   cd file-combiner
   ```
3. Set up development environment:
   ```bash
   make install-dev
   ```
1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes and add tests
3. Run tests and linting:
   ```bash
   make test
   make lint
   ```
4. Format your code:
   ```bash
   make format
   ```
5. Commit your changes:
   ```bash
   git commit -m "Add your descriptive commit message"
   ```
6. Push to your fork and submit a pull request
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Add docstrings for all public functions and classes
- Write tests for new functionality
- Keep functions focused and small
- Use meaningful variable and function names
- Add unit tests for new features
- Ensure all tests pass before submitting PR
- Test with different Python versions (3.8+)
- Include integration tests for complex features
- Update README.md if adding new features
- Add docstrings to new functions
- Update examples if changing CLI interface
- Provide a clear description of changes
- Reference any related issues
- Include screenshots for UI changes
- Ensure CI passes
Thank you for contributing!