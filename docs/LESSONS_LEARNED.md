# Lessons Learned: Developing the Weather Agent

This document summarizes key insights and takeaways from building the Agentic AI Weather Assistant.

## 1. RAG with High-Density Numerical Data is Radically Different
Traditional RAG systems (Retrieval-Augmented Generation) are built for text. You chunk a document, embed it, store it in a vector database, and retrieve semantic matches.
**Lesson:** This approach completely fails for numerical weather data. Gridded meteorological data (temperature, humidity matrices) lacks semantic meaning to an embedding model. Instead, we had to adopt an **API-centric RAG approach**. We bypassed vector databases entirely for real-time forecasting, writing tools that query the NWP API directly, parse the JSON, and inject the trimmed, structured raw data directly into the LLM context.

## 2. LLMs Will Hallucinate Weather if Not Tightly Constrained
By default, Large Language Models want to be helpful. If you ask a generic base model "Will it rain in Delhi tomorrow?" without context, it will often confidently fabricate an answer based on its training weights rather than admitting ignorance.
**Lesson:** System prompts must strictly constrain the agent. We implemented a strict "refusal" policy: if the retrieval tool fails to fetch the latest API data, the LLM is instructed to output an error rather than guessing. Prompt engineering for **verification** is just as important as prompt engineering for **generation**.

## 3. Spatial PDF Parsing is the Bottleneck of Document Retrieval
Weather organizations often publish critical warnings in PDFs designed for human readability, not machine extraction. Standard libraries (like PyPDF2) read text linearly, destroying the spatial relationships of tables.
**Lesson:** We had to rely on `pdfplumber` to extract bounding boxes and reconstruct tables. However, this parsing logic is brittle. If the layout of the bulletin changes by a few pixels, the extraction fails. Future iterations must look toward Vision-Language Models (VLMs) that can "read" the PDF visually rather than relying on regex parsing.

## 4. Local Execution is Viable but Context-Constrained
Running a 7B parameter model (Zephyr) locally via `llama.cpp` proved highly successful for preserving data privacy.
**Lesson:** The primary limitation of local inference isn't the reasoning capability—it's the context window. Weather API JSONs are massive. We spent a significant amount of engineering effort writing functions to trim useless JSON keys (like internal server IDs and redundant timestamps) before passing the payload to the LLM, in order to prevent Out-Of-Memory (OOM) errors on our local HPC nodes.

## 5. Tool Selection Requires Explicit Descriptions
When using a ReAct agent, the LLM must autonomously decide which function to execute. Initially, the agent would get confused between the `fetch_hourly_data` tool and the `fetch_daily_data` tool.
**Lesson:** Tool descriptions (the docstrings passed to the LLM) must be incredibly explicit. Adding clear boundaries (e.g., "Use this tool ONLY if the user explicitly asks for hourly breakdowns. Otherwise, default to the daily tool.") drastically improved routing accuracy.
