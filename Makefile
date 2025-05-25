PYTHON = python3
PDM = pdm
PACKAGE_NAME = file-combiner
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
BLUE = \033[0;34m
NC = \033[0m
.PHONY: help install install-dev install-user test test-coverage lint typecheck format clean examples github-demo run-help demo
help:
	@echo "$(GREEN)File Combiner (PDM) - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup (PDM-based):$(NC)"
	@echo "  make install         - Install dependencies with PDM"
	@echo "  make install-dev     - Install with development dependencies"
	@echo "  make install-user    - Install for current user (pip fallback)"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  make test            - Run all tests"
	@echo "  make test-coverage   - Run tests with coverage"
	@echo "  make lint            - Check code style"
	@echo "  make typecheck       - Run type checking with mypy"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make format          - Format code with black"
	@echo "  make clean           - Clean temporary files"
	@echo "  make examples        - Run local examples"
	@echo "  make github-demo     - Demo GitHub URL support"
install:
	@echo "$(GREEN)Installing dependencies with PDM...$(NC)"
	$(PDM) install
	@echo "$(GREEN)✓ Installation complete!$(NC)"
install-dev:
	@echo "$(GREEN)Installing with development dependencies...$(NC)"
	$(PDM) install -G dev
	@echo "$(GREEN)✓ Development installation complete!$(NC)"
install-user:
	@echo "$(GREEN)Installing for current user (pip fallback)...$(NC)"
	$(PYTHON) -m pip install --user .
	@echo "$(GREEN)✓ User installation complete!$(NC)"
test:
	@echo "$(GREEN)Running tests...$(NC)"
	$(PDM) run pytest tests/ -v
test-coverage:
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PDM) run pytest tests/ --cov=file_combiner --cov-report=html
lint:
	@echo "$(GREEN)Checking code style...$(NC)"
	$(PDM) run flake8 file_combiner.py tests/
	$(PDM) run black --check file_combiner.py tests/
typecheck:
	@echo "$(GREEN)Running type checking...$(NC)"
	$(PDM) run mypy file_combiner.py
format:
	@echo "$(GREEN)Formatting code...$(NC)"
	$(PDM) run black file_combiner.py tests/
	@echo "$(GREEN)✓ Code formatted!$(NC)"
clean:
	@echo "$(GREEN)Cleaning temporary files...$(NC)"
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "__pypackages__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .pdm-build/
	rm -f examples/combined.txt examples/demo.txt examples/github-*.txt
	@echo "$(GREEN)✓ Cleanup complete!$(NC)"
examples:
	@echo "$(GREEN)Running local examples...$(NC)"
	@mkdir -p examples/demo
	@echo "print('Hello from file-combiner!')" > examples/demo/test.py
	@echo "# Demo Project" > examples/demo/README.md
	@echo "console.log('Hello');" > examples/demo/script.js
	file-combiner combine examples/demo examples/combined.txt --verbose \
		--exclude "__pycache__/**" --exclude "*.pyc"
	file-combiner split examples/combined.txt examples/restored
	@echo "$(GREEN)✓ Local examples completed!$(NC)"
github-demo:
	@echo "$(BLUE)Running GitHub URL demo...$(NC)"
	@echo "$(YELLOW)Testing GitHub repository cloning and combining...$(NC)"
	file-combiner combine https://github.com/davidlu1001/file-combiner examples/github-demo.txt \
		--exclude "__pycache__/**" --exclude ".git/**" \
		--exclude "*.pyc" --exclude ".pytest_cache/**" \
		--exclude "__pypackages__/**" --dry-run --verbose
	@echo "$(GREEN)✓ GitHub demo completed!$(NC)"
run-help:
	file-combiner --help
demo:
	file-combiner combine . demo.txt --dry-run --verbose \
		--exclude "__pycache__/**" --exclude "__pypackages__/**"