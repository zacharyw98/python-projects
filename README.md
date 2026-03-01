# Python Projects

A collection of Python projects I have built over the past two years, mostly focused on AI systems, automation, and tools. Most of this work started with an idea, a conversation with an AI to figure out if it was buildable, and then me writing the code and debugging until it worked.

---

## AIDA - Custom AI Agent

**Files:** `new_aida.py`, `mitaida.py`

AIDA is the project I have put the most work into. It started as an experiment with custom persona prompt injections - trying to see how far you could shape an AI's behavior through the system prompt alone. That led to building an emotion system to measure and refine those prompts, which eventually grew into a full agent framework.

The final version is built with LangGraph and runs every message through a pipeline of nodes before generating a response:

- An emotional engine that tracks Joy, Curiosity, Frustration, and Stress using a 39-word lexicon
- A sandboxed math processor for inline calculations
- A file loader that reads and persists content to memory
- An adaptive control system that automatically damps stress if it gets too high
- Persistent JSON memory so AIDA remembers facts and emotional state between sessions

Runs locally with Ollama or through OpenRouter for cloud models.

**Requires:** `langgraph`, `requests`, `ollama` (or OpenRouter API key)

---

## AI Sycophancy Research Tool

**File:** `aitester.py`

I got interested in why AI models tend to agree with users even when the user is wrong. This tool was built to study that in a structured way.

It scores AI responses for sycophantic patterns using weighted analysis across four categories - first-person language, agreement phrases, emotional language, and AI self-identification phrases. Scores range from 0 to 100.

Includes a GUI terminal with a live scoring meter, word count, vocabulary diversity tracking, and CSV export so you can log and compare results across models over time.

I used this to run structured multi-act tests on Mistral and Copilot. The results confirmed that different prompting styles produce significantly different sycophancy levels in the same model.

**Requires:** `FreeSimpleGUI`

---

## Behavioral Priority Engine

**Files:** `BPEAI.py`, `bpe_simulator.py`

An experiment in using a weighted cognitive profile to shape how an AI model reasons and responds. The idea was to define a set of behavioral traits with percentage weights - things like Communication (14%), Memory Recall (8%), Imagination (8%) - and inject that profile into the system prompt to constrain the model's behavior.

`BPEAI.py` runs against a local Ollama model. `bpe_simulator.py` uses the Google Gemini API.

To use `bpe_simulator.py`, set your Gemini API key as an environment variable:
```
set GEMINI_API_KEY=your_key_here
```

**Requires:** `requests`, `ollama` or `google-generativeai`

---

## Wowhead Scraper and Market Price Monitor

**Files:** `wowhead_scraper.py`, `WOWmonitor3.py`

A scraper that pulls item data from Wowhead, a large MMORPG database. The scraper runs asynchronously with a configurable concurrency limit and handles pagination, retries, timeouts, and graceful shutdown on Ctrl+C so progress is never lost.

Ended up extracting 286,801 item records across multiple runs.

The output feeds into a market price monitor that tracks in-game auction house prices using the scraped item IDs. Results are saved to JSON and CSV.

Settings like scan block size, concurrency limit, keyword filters, and output filenames are all configurable through `settings.json` which the script generates on first run.

**Requires:** `requests`, `beautifulsoup4`, `aiohttp`, `tqdm`

---

## AIDA: Master Expedition - Dungeon Crawler Game

**File:** `rpg.py`

A fully playable dungeon crawler built with pygame. Named after AIDA because it was originally built using a Gemini session with a custom persona prompt injection as a development collaborator - the same experiment that sparked the AIDA agent work.

The technically interesting parts are underneath the game:

- BFS pathfinding written from scratch so enemies navigate around walls to reach the player
- A fallback wall-drilling algorithm that guarantees a path always exists even in badly generated dungeons
- Bresenham's line algorithm for line of sight - walls correctly block the player's torch vision
- Procedural dungeon generation with maps that expand as you descend
- Four playable classes (Warrior, Mage, Rogue, Cleric) with different stats and skills
- Save and load system using JSON, inn rest points, and permadeath if no save exists

**Requires:** `pygame`, `pygame_gui`

---

## OpenRouter Model Manager

**File:** `routeraiapi.py`

Connects to the OpenRouter API, fetches the full list of available models, and splits them into two JSON files - free models and paid models. Stores your API key locally in `config.json` so you only have to enter it once.

Useful as a reference when picking models for other projects.

**Requires:** `requests`

---

## Setup

Most projects need a few pip installs. The main ones across all projects are:

```
pip install requests beautifulsoup4 aiohttp tqdm langgraph FreeSimpleGUI pygame pygame_gui google-generativeai
```

For projects that use local models, you need Ollama installed and running:
- Download from https://ollama.com
- Pull a model: `ollama pull mistral`
- Make sure `ollama serve` is running before starting the script

---

## About

Self-taught Python developer. These projects were built to solve problems I found interesting, learn how AI systems actually behave under different conditions, and get better at Python by building real things rather than following tutorials.