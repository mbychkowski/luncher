.PHONY: run-backend install-deps run-agent playground eval deploy clean help

# Default target
help:
	@echo "🍔 Luncher Workshop Makefile"
	@echo "Available commands:"
	@echo "  make install-deps   Install project and agent dependencies"
	@echo "  make run-backend    Start the mock Luncher Flask API (port 8080)"
	@echo "  make run-agent      Run a single test prompt through the agent CLI"
	@echo "  make playground     Open the interactive web playground"
	@echo "  make eval           Run systematic evaluations against evalsets"
	@echo "  make deploy         Deploy the agent to Cloud Run / Agent Platform"
	@echo "  make clean          Clean up pycache and temporary files"

install-deps:
	uv tool install google-agents-cli
	@if [ -d "agents/luncher-agent" ]; then \
		cd agents/luncher-agent && uv sync --prerelease=allow; \
	fi

run-backend:
	@echo "Starting Luncher Flask API..."
	python apps/luncher-api/app/main.py

run-agent:
	@if [ ! -d "agents/luncher-agent" ]; then \
		echo "Error: agents/luncher-agent/ directory not found. Please scaffold the agent first (Exercise 1)!"; \
		exit 1; \
	fi
	cd agents/luncher-agent && agents-cli run "Organize a Technical Kickoff for Alice, Bob, and Charlie"

playground:
	@if [ ! -d "agents/luncher-agent" ]; then \
		echo "Error: agents/luncher-agent/ directory not found. Please scaffold the agent first (Exercise 1)!"; \
		exit 1; \
	fi
	cd agents/luncher-agent && agents-cli playground

eval:
	@if [ ! -d "agents/luncher-agent" ]; then \
		echo "Error: agents/luncher-agent/ directory not found. Please scaffold the agent first (Exercise 1)!"; \
		exit 1; \
	fi
	cd agents/luncher-agent && agents-cli eval run --all

deploy:
	@if [ ! -d "agents/luncher-agent" ]; then \
		echo "Error: agents/luncher-agent/ directory not found. Please scaffold the agent first (Exercise 1)!"; \
		exit 1; \
	fi
	cd agents/luncher-agent && agents-cli deploy

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
