# Future Roadmap

This document outlines the planned future enhancements for the Agentic AI Weather Assistant, focusing on system scalability, capability expansion, and multi-modal integration.

## Phase 1: Enhanced Retrieval & Data Sources

- **Radar & Satellite Integration (Vision LLMs):** 
  Transition from pure text-based retrieval to multi-modal reasoning. By integrating models like LLaVA or GPT-4o, the agent could ingest Doppler radar imagery and generate natural language descriptions of storm cell movements.
- **Ensemble Forecasting Support:** 
  Currently, the system queries a deterministic model. The goal is to query ensemble models (EPS) and have the LLM synthesize probability percentiles (e.g., "There is a 70% chance of rain, and a 30% chance of severe thunderstorms").
- **Agromet Advisory Integration:** 
  Add domain-specific tool layers to fetch agricultural advisories, allowing farmers to ask queries like, "Should I sow my seeds this week in Punjab?"

## Phase 2: Agentic Architecture Upgrades

- **Multi-Agent Orchestration:** 
  Shift from a single ReAct agent to a hierarchical multi-agent framework (e.g., LangGraph or AutoGen). 
  - *Agent 1 (Router):* Classifies query intent.
  - *Agent 2 (Data Fetcher):* Interacts with APIs.
  - *Agent 3 (Reviewer):* Fact-checks the generated output against the raw JSON before final delivery.
- **Streaming Context Synthesis:** 
  Implement token-streaming from the LLM back to the client interface to reduce perceived latency, while the retrieval layer operates asynchronously in the background.

## Phase 3: Deployment & Infrastructure

- **VLLM / TGI Serving:** 
  Transition local inference from `llama.cpp` to high-throughput serving engines like `vLLM` or HuggingFace Text Generation Inference (TGI) to support concurrent user queries on the HPC cluster.
- **Voice-to-Voice Pipelines:** 
  Integrate robust Speech-to-Text (STT) and Text-to-Speech (TTS) models (such as Whisper and XTTS) to deploy the assistant via telephone IVR systems or dedicated mobile apps, improving accessibility for rural populations.
- **Continuous LoRA Fine-Tuning Pipeline:** 
  Automate the ingestion of corrected user interactions into the `finetuning_dataset.jsonl` and schedule weekly LoRA training jobs to continuously improve the model's domain vocabulary.
