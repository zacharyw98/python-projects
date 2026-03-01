# Python Projects

A collection of Python projects built over the past two years, mostly focused on AI systems, automation, and tools. Most of this work started with an idea, a conversation with an AI to figure out if it was buildable, and then writing the code and debugging until it worked.

---

## AIDA - Custom AI Agent (Flagship Project)

**Files:** `AIDA.py` (v2.4 - current), `new_aida.py`, `mitaida.py` (earlier versions)

AIDA started as an experiment with custom persona prompt injections - trying to see how far you could push an AI's behavior through the system prompt alone. That led to building an emotion system to measure and refine those prompts, which grew into a full agent framework over multiple versions.

`AIDA.py` is the most complete version. It runs every message through a seven-node LangGraph pipeline:

- Emotional engine tracking Joy, Curiosity, Frustration, and Stress using a 39-word lexicon with per-word affinity deltas
- Adaptive Control System that caps stress at a hard ceiling and applies graduated damping before it gets there
- Sandboxed math processor for inline calculations using [CALC: expr] syntax
- File loader that chunks Python files by function and class using the AST and stores them in the knowledge base
- Semantic RAG retrieval using sentence-transformers embeddings with recency boost and source diversity filtering
- Synthesis node that adjusts token budget, history depth, and prompt complexity based on current stress level
- Model fallback chain - tries Mistral first, falls back to phi3:mini then llama3.2:1b if it times out

Other features in v2.4:
- Persistent memory across sessions - facts, entities, conversation history, and emotional state all survive restarts
- Automatic conversation summarisation when history gets too long, stored back into the knowledge base
- Entity extraction from responses with a blocklist and proper-noun filter to cut down on noise
- COMMIT: syntax for storing facts directly without an LLM call
- Waking summary on the first turn of each session showing how long since the last conversation
- Prompt-bleed sanitiser that strips system prompt fragments Mistral sometimes echoes back into responses

**Requires:** `langgraph`, `requests`, `sentence-transformers`, `scipy`

---

## AI Sycophancy Research Tool

**File:** `aitester.py`

Built to study why AI models tend to agree with users even when the user is wrong.

Scores AI responses for sycophantic patterns using weighted analysis across four categories - first-person language, agreement phrases, emotional language, and AI self-identification phrases. Scores range from 0 to 100.

Includes a GUI terminal with a live scoring meter, word count, vocabulary diversity tracking, and CSV export so results can be logged and compared across models over time. Ran structured multi-act tests on Mistral and Copilot - confirmed that different prompting styles produce significantly different sycophancy levels in the same model.

**Requires:** `FreeSimpleGUI`

---

## Behavioral Priority Engine

**Files:** `BPEAI.py`, `bpe_simulator.py`

An experiment in using a weighted cognitive profile to shape how an AI model reasons and responds. Defines 18 behavioral traits with percentage weights - Communication (14%), Memory Recall (8%), Imagination (8%), and so on - then injects that profile into the system prompt to constrain model behavior.

`BPEAI.py` runs against a local Ollama model. `bpe_simulator.py` uses the Google Gemini API.

To use `bpe_simulator.py`, set your Gemini API key as an environment variable:
```
set GEMINI_API_KEY=your_key_here
```

**Requires:** `requests`, `ollama` or `google-generativeai`

---

## Wowhead Scraper and Market Price Monitor

**Files:** `wowhead_scraper.py`, `WOWmonitor3.py`

A scraper that pulls item data from Wowhead, a large MMORPG database. Runs asynchronously with a configurable concurrency limit and handles pagination, retries, timeouts, and graceful shutdown on Ctrl+C so progress is never lost. Extracted 286,801 item records across multiple runs.

The output feeds into a market price monitor that tracks in-game auction house prices using the scraped item IDs. Settings like scan block size, concurrency limit, keyword filters, and output filenames are all configurable through `settings.json` which the script creates on first run.

**Requires:** `requests`, `beautifulsoup4`, `aiohttp`, `tqdm`

---

## AIDA: Master Expedition - Dungeon Crawler Game

**File:** `rpg.py`

A fully playable dungeon crawler built with pygame. Named after AIDA because it was originally built using a Gemini session with a custom persona prompt injection as a development collaborator - the same experiment that sparked the AIDA agent work.

What makes it technically interesting underneath the game:
- BFS pathfinding written from scratch so enemies navigate around walls to reach the player
- A fallback wall-drilling algorithm that guarantees a path always exists even in badly generated dungeons
- Bresenham's line algorithm for line of sight - walls correctly block the player's torch vision
- Procedural dungeon generation with maps that expand as you descend
- Four playable classes (Warrior, Mage, Rogue, Cleric) with unique stats and skills
- Save and load system using JSON, inn rest points, and permadeath if no save exists

**Requires:** `pygame`, `pygame_gui`

---

## OpenRouter Model Manager

**File:** `routeraiapi.py`

Connects to the OpenRouter API, fetches the full list of available models, and splits them into two JSON files - free models and paid models. Stores your API key locally in `config.json` so you only have to enter it once.

**Requires:** `requests`

---

## Setup

```
pip install requests beautifulsoup4 aiohttp tqdm langgraph sentence-transformers scipy FreeSimpleGUI pygame pygame_gui google-generativeai
```

For projects that use local models, you need Ollama installed and running:
- Download from https://ollama.com
- Pull a model: `ollama pull mistral`
- Run `ollama serve` before starting the script

---

## About

Self-taught Python developer. These projects were built to solve problems I found interesting, learn how AI systems actually behave under different conditions, and get better at Python by building real things rather than following tutorials.
