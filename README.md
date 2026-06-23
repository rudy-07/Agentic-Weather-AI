# Agentic AI Weather Assistant

This repository contains the codebase for the Agentic AI Weather Assistant, an autonomous system built on a Retrieval-Augmented Generation (RAG) architecture that interfaces with the Mausamgram API and IMD bulletins.

## Features
- **Agentic Orchestrator**: Uses LangChain and local LLMs to interpret natural language weather queries.
- **Dynamic Retrieval Layer**: Fetches real-time gridded NWP data via the Mausamgram API and parses PDF bulletins using `pdfplumber`.
- **Local Inference**: Supports running quantized models (e.g., Zephyr-7B GGUF) locally via `llama.cpp` for privacy and offline capability.
- **Location Resolution**: Maps plain text locations to coordinates.

## Setup

1. Copy `.env.example` to `.env` and fill in your configurations:
   ```bash
   cp .env.example .env
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

To run the agent interactively:
```bash
python run_agent.py --agent
```

To run a direct forecast fetch:
```bash
python run_agent.py --place "Lucknow" --forecast daily
```

## Structure
- `run_agent.py`: Main entry point for the agentic orchestrator.
- `tools.py`: Contains API integration tools (Mausamgram, IMD scraper).
- `finetune.py` / `fix_dataset.py`: Utilities for LoRA fine-tuning local models.
