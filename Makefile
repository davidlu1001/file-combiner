PYTHON = python3
PACKAGE_NAME = file-combiner
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m
.PHONY: help install test clean format lint
help:
	@echo "$(GREEN)File Combiner (Python) - Available Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup:$(NC)"
	@echo "  make install         - Install file-combiner"
	@echo "  make install-dev     - Install in development mode"
	@echo "  make install-user    - Install for current user"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  make test            - Run all tests"
	@echo "  make test-coverage   - Run tests with coverage"
	@echo "  make lint            - Check code style"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make format          - Format code with black"
	@echo "  make clean           - Clean temporary files"
	@echo "  make examples        - Run examples"
install:
	@echo "$(GREEN)Installing file-combiner...$(NC)"
	$(PYTHON) -m pip install .
	@echo "$(GREEN)✓ Installation complete!$(NC)"
install-dev:
	@echo "$(GREEN)Installing in development mode...$(NC)"
	$(PYTHON) -m pip install -e ".[dev,full]"
	@echo "$(GREEN)✓ Development installation complete!$(NC)"
install-user:
	@echo "$(GREEN)Installing for current user...$(NC)"
	$(PYTHON) -m pip install --user .
	@echo "$(GREEN)✓ User installation complete!$(NC)"
test:
	@echo "$(GREEN)Running tests...$(NC)"
	$(PYTHON) -m pytest tests/ -v
test-coverage:
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PYTHON) -m pytest tests/ --cov=file_combiner --cov-report=html
lint:
	@echo "$(GREEN)Checking code style...$(NC)"
	$(PYTHON) -m flake8 file_combiner.py tests/
	$(PYTHON) -m black --check file_combiner.py tests/
format:
	@echo "$(GREEN)Formatting code...$(NC)"
	$(PYTHON) -m black file_combiner.py tests/
	@echo "$(GREEN)✓ Code formatted!$(NC)"
clean:
	@echo "$(GREEN)Cleaning temporary files...$(NC)"
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/
	@echo "$(GREEN)✓ Cleanup complete!$(NC)"
examples:
	@echo "$(GREEN)Running examples...$(NC)"
	@mkdir -p examples/demo
	@echo "print('Hello')" > examples/demo/test.py
	@echo "# Demo" > examples/demo/README.md
	$(PYTHON) file_combiner.py combine examples/demo examples/combined.txt --verbose
	$(PYTHON) file_combiner.py split examples/combined.txt examples/restored
	@echo "$(GREEN)✓ Examples completed!$(NC)"
run-help:
	$(PYTHON) file_combiner.py --help
demo:
	$(PYTHON) file_combiner.py combine . demo.txt --dry-run --verbose