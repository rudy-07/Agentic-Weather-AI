# Engineering Decisions & Trade-offs

This document chronicles the major architectural and engineering decisions made during the development of the Agentic AI Weather Assistant. 

## 1. Dual Local vs. Cloud Inference Architecture

### The Problem
Processing sensitive internal meteorological data requires strict data privacy, preventing the use of standard commercial cloud LLMs (like OpenAI GPT-4 or Anthropic Claude) for certain tasks. However, relying solely on local models can limit reasoning capabilities and requires significant dedicated hardware.

### The Decision
We implemented a dynamic, abstracted LLM layer that supports both **Cloud Inference** (via Hugging Face API / Gemma) and **Local Inference** (via Llama.cpp / Zephyr-7B).

### Trade-offs
- **Cloud API:**
  - *Pros:* Higher reasoning quality, zero local infrastructure maintenance, handles highly ambiguous queries effectively.
  - *Cons:* Network latency, strict data privacy concerns, API rate limits.
- **Local HPC (GGUF Quantization):**
  - *Pros:* 100% data security, reliable offline execution, no recurring API costs.
  - *Cons:* Requires GPU clusters, managing context windows is challenging due to limited VRAM, lower capability on edge-case reasoning compared to trillion-parameter models.

## 2. RAG Over Numerical APIs vs. Vector Databases

### The Problem
Standard RAG architectures rely on chunking text and storing it in a Vector Database (like Pinecone or Milvus). However, weather forecasting relies on high-resolution numerical grids (NWP) which update constantly and lose their meaning if chunked into text.

### The Decision
We opted for a **Tool-Based / API-Centric RAG** approach rather than a Vector DB approach. The agent interacts with live APIs to pull real-time numerical JSON arrays and dynamically injects them into the prompt. Vector databases were entirely omitted from the core forecasting loop.

### Trade-offs
- *Pros:* Guarantees the LLM is citing the absolute latest numerical forecast; removes the complexity of continuous vector DB synchronization.
- *Cons:* Raw JSON consumes a massive amount of the LLM's context window. We had to build aggressive data trimming layers to strip out useless JSON keys before feeding it to the LLM.

## 3. Spatial PDF Parsing for Unstructured Data

### The Problem
National weather warnings and synoptic features are often distributed as complex, multi-column PDFs containing non-standard tables. Standard text extraction tools (like PyPDF2) destroy the spatial relationship of table columns, causing the LLM to misinterpret warnings (e.g., assigning a heavy rain warning to the wrong state).

### The Decision
We engineered a custom extraction pipeline using `pdfplumber` relying heavily on spatial tolerances and regex pattern matching to identify table headers and rebuild them into structured dictionaries before passing them to the agent.

### Trade-offs
- *Pros:* Drastically reduced LLM hallucination rates on regional warnings.
- *Cons:* The parser logic is brittle; if the format of the official PDF bulletin changes, the regex and bounding-box rules require manual updates.

## 4. Parameter-Efficient Fine-Tuning (PEFT)

### The Problem
The base open-source models struggled to understand specific meteorological terminology (e.g., "synoptic trough," "cyclonic circulation") and often formatted their responses poorly.

### The Decision
Instead of full-parameter fine-tuning, we utilized **LoRA (Low-Rank Adaptation)** via the `TRL` library. We trained adapters on proprietary QA datasets to align the model's tone and domain vocabulary.

### Trade-offs
- *Pros:* We could train the model on a single HPC GPU node in hours instead of weeks. The resulting adapter weights were small (megabytes), making deployment trivial.
- *Cons:* LoRA fine-tuning improves tone and formatting but does not fundamentally inject new factual weather knowledge—hence, the reliance on the RAG pipeline remained critical.
