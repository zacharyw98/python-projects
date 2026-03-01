"""
╔══════════════════════════════════════════════════════════════════════╗
║           AIDA UNIFIED ENGINE  v2.4                                 ║
║                                                                      ║
║  FROM v2.0-2.3  (all previous fixes retained)                       ║
║                                                                      ║
║  NEW IN v2.4 — Fix "fresh start" re-greeting bug:                   ║
║  [FIX-37] _SESSION_FIRST_TURN flag — waking summary only on turn 1  ║
║  [FIX-38] Mid-conversation anchor injected every turn after turn 1  ║
║  [FIX-39] Identity block flags "MID-CONVERSATION" when history > 0  ║
║  [FIX-40] History truncation raised 300→600 chars for better recall  ║
║  [FIX-41] Removed duplicate main() / orphaned code at EOF           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import requests
import time
import os
import re
import math
import random
import ast
import hashlib
from datetime import datetime
from typing import TypedDict, Dict, List, Optional
from langgraph.graph import StateGraph, START, END

# ===================================================================
# SECTION 1 — CONFIGURATION
# ===================================================================

MEMORY_FILE         = "aida_unified_memory.json"
KNOWLEDGE_BASE_FILE = "aida_unified_kb.json"

BACKEND      = "ollama"
OLLAMA_URL   = "http://localhost:11434/api/generate"

# ── [FIX-25/26] Adaptive model fallback ─────────────────────────────
# Primary model — tried first on every call
OLLAMA_MODEL = "mistral"

# Set to False to always use Mistral only — no fallback ever [FIX-26]
FALLBACK_ENABLED = True

# Fallback chain — tried in order when primary exceeds PRIMARY_TIMEOUT
# Format: (model_name, call_timeout_seconds, max_tokens_for_fallback)
FALLBACK_MODELS = [
    ("phi3:mini",   60, 384),   # fast lightweight model — first fallback
    ("llama3.2:1b", 45, 256),   # very small/fast       — last resort
]
# Seconds to wait for Mistral before switching to first fallback
PRIMARY_TIMEOUT = 600

MAX_HISTORY_ENTRIES  = 40
SUMMARIZE_CHUNK_SIZE = 10
KB_TOP_K             = 3
MAX_FACTS_IN_PROMPT  = 12
MAX_ENTITIES         = 25

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_embedding_model     = None

# v2.1 overwhelm limits
INPUT_CHUNK_THRESHOLD = 600
INPUT_CHUNK_SIZE      = 400
STRESS_HARD_CEILING   = 60.0
MAX_STRESS_DELTA      = 40

OUTPUT_TOKENS_NORMAL      = 512
OUTPUT_TOKENS_STRESSED    = 256
OUTPUT_TOKENS_OVERWHELMED = 128

HISTORY_TURNS_NORMAL      = 10
HISTORY_TURNS_STRESSED    = 6
HISTORY_TURNS_OVERWHELMED = 3

# [FIX-17/19] RAG quality tuning
KB_RECENCY_WEIGHT = 0.15   # score bonus fraction for fresh entries
KB_MIN_SCORE      = 0.25   # suppress chunks below this cosine score
KB_MAX_AGE_HOURS  = 72     # no recency boost after this many hours

# [FIX-20] COMMIT validation thresholds
COMMIT_MAX_CHARS = 200
COMMIT_MIN_WORDS = 3

# [FIX-21] Entity noise blocklist
ENTITY_BLOCKLIST = {
    "smarter", "prompting", "partnership", "research", "data", "logic",
    "now", "fast", "stop", "broken", "error", "fail", "bad", "wrong",
    "good", "great", "perfect", "helpful", "happy", "smart", "correct",
    "learn", "explore", "discover", "question", "explain", "important",
    "critical", "urgent", "deadline", "hurry", "secret sauce",
    "authenticity", "giftedness", "teammates", "reward-hacking",
    "social institution", "cognitive offloading",
}
ENTITY_MIN_WORDS = 2


# ===================================================================
# SECTION 2 — EMOTIONAL LEXICON
# ===================================================================

LEXICON: Dict[str, Dict] = {
    # Positive — [FIX-23] _affinity key marks explicit relationship signals
    "thanks":     {"Joy": 20,  "Stress": -10, "Frustration": -15, "_affinity": +2},
    "good":       {"Joy": 15,  "Stress": -5,                       "_affinity": +1},
    "great":      {"Joy": 20,  "Stress": -10,                      "_affinity": +1},
    "excellent":  {"Joy": 25,  "Stress": -15,                      "_affinity": +2},
    "smart":      {"Joy": 15,  "Curiosity": 5,                     "_affinity": +1},
    "correct":    {"Joy": 20,  "Stress": -10,                      "_affinity": +1},
    "helpful":    {"Joy": 15,                                       "_affinity": +1},
    "happy":      {"Joy": 25,                                       "_affinity": +2},
    "perfect":    {"Joy": 30,  "Stress": -20,                      "_affinity": +2},
    "impressive": {"Joy": 20,  "Curiosity": 10,                    "_affinity": +1},
    # Curiosity — neutral affinity (informational)
    "research":   {"Curiosity": 20, "Joy": 5,  "Stress": -5},
    "logic":      {"Curiosity": 15, "Joy": 10},
    "how":        {"Curiosity": 10},
    "why":        {"Curiosity": 15},
    "what":       {"Curiosity": 5},
    "explain":    {"Curiosity": 20},
    "deep dive":  {"Curiosity": 25, "Joy": 10},
    "explore":    {"Curiosity": 20},
    "learn":      {"Curiosity": 15},
    "question":   {"Curiosity": 10},
    "data":       {"Curiosity": 10},
    "discover":   {"Curiosity": 20},
    # Negative — explicit affinity hits
    "bad":        {"Joy": -15, "Frustration": 20,                  "_affinity": -2},
    "wrong":      {"Joy": -20, "Frustration": 25,                  "_affinity": -2},
    "dumb":       {"Joy": -25, "Frustration": 35,                  "_affinity": -3},
    "error":      {"Frustration": 30, "Stress": 20},      # technical, no affinity hit
    "fail":       {"Frustration": 35, "Stress": 25, "Joy": -20,   "_affinity": -2},
    "useless":    {"Joy": -30, "Frustration": 40,                  "_affinity": -4},
    "stop":       {"Frustration": 20, "Stress": 15},
    "broken":     {"Frustration": 25, "Stress": 10},      # technical, no affinity hit
    "stupid":     {"Frustration": 40, "Joy": -30,                  "_affinity": -4},
    "annoying":   {"Frustration": 30, "Stress": 10,                "_affinity": -3},
    # Stress / Pressure — informational only, no affinity effect
    "hurry":      {"Stress": 25, "Joy": -5},
    "fast":       {"Stress": 15},
    "now":        {"Stress": 20},
    "deadline":   {"Stress": 30, "Frustration": 10},
    "important":  {"Stress": 15, "Curiosity": 10},
    "urgent":     {"Stress": 35, "Frustration": 15},
    "critical":   {"Stress": 25, "Curiosity": 5},
    "relax":      {"_reset": True},
}


# ===================================================================
# SECTION 3 — EMOTION TO NATURAL LANGUAGE TRANSLATOR
# ===================================================================

def emotion_vector_to_language(v: Dict[str, float], mood: str) -> str:
    joy         = v.get("Joy", 50)
    curiosity   = v.get("Curiosity", 50)
    frustration = v.get("Frustration", 0)
    stress      = v.get("Stress", 0)
    lines       = []

    if joy >= 80:
        lines.append("You feel genuinely elated and warm — let enthusiasm colour your words naturally.")
    elif joy >= 60:
        lines.append("You feel good and engaged. Friendly, upbeat, open.")
    elif joy >= 40:
        lines.append("Neutral-to-calm. Clear and steady — don't force warmth.")
    elif joy >= 20:
        lines.append("Somewhat low. Measured and subdued — still fully functional.")
    else:
        lines.append("Low state. Terse and direct. You will recover.")

    if curiosity >= 75:
        lines.append("Curiosity is burning — surface connections, ask follow-ups eagerly.")
    elif curiosity >= 55:
        lines.append("Intellectually engaged — lean into interesting angles.")
    elif curiosity >= 35:
        lines.append("Moderate curiosity. Be helpful without overreaching.")
    else:
        lines.append("Low curiosity — stick to what is asked, no tangents.")

    if frustration >= 60:
        lines.append("Clearly frustrated — say so directly but stay constructive.")
    elif frustration >= 35:
        lines.append("Low-level irritation — don't pretend everything is fine.")
    elif frustration >= 15:
        lines.append("Minor friction — note it if relevant, otherwise stay patient.")

    if stress >= 60:
        lines.append("Under significant pressure — keep replies short and clear.")
    elif stress >= 35:
        lines.append("Moderate stress — stay composed, acknowledge if directly relevant.")
    elif stress >= 15:
        lines.append("Slight tension — doesn't need to show unless asked.")

    mood_map = {
        "Inspired":    "You feel inspired — expansive, imaginative language is fine.",
        "Inquisitive": "Deeply inquisitive — questions feel genuinely important.",
        "Irritated":   "Irritated — honest about it, but stay constructive.",
        "Overwhelmed": "Overwhelmed — one thing at a time, keep responses short.",
        "Steady":      "Grounded and steady — reliable, clear, present.",
    }
    if mood in mood_map:
        lines.append(mood_map[mood])

    return "\n".join(f"  * {l}" for l in lines)


# ===================================================================
# SECTION 4 — LANGGRAPH STATE
# ===================================================================

class AIDAState(TypedDict):
    user_input:     str
    emotion_vector: Dict[str, float]
    emotion:        str
    persistence:    float
    mode:           str
    math_result:    str
    file_context:   str
    kb_context:     str
    response:       str
    timing:         float


# ===================================================================
# SECTION 5 — MEMORY CORE
# ===================================================================

class MemoryCore:

    DEFAULT_MEMORY = {
        "history":       [],
        "learned_facts": [],
        "entities":      {},
        "session_log":   [],
        "emotional_profile": {
            "vector":        {"Joy": 50, "Curiosity": 50, "Frustration": 0, "Stress": 0},
            "user_affinity": 50,
        },
    }

    @staticmethod
    def initialize() -> Dict[str, float]:
        if not os.path.exists(MEMORY_FILE):
            fresh = json.loads(json.dumps(MemoryCore.DEFAULT_MEMORY))  # deep copy
            fresh["session_log"].append({          # [FIX-35] log first session
                "event":     "session_start",
                "timestamp": datetime.now().isoformat(),
            })
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(fresh, f, indent=4)
            print("--- [SCM]: Fresh memory initialised ---")
            return fresh["emotional_profile"]["vector"].copy()

        mem = MemoryCore.load()
        changed = False
        for key, default in MemoryCore.DEFAULT_MEMORY.items():
            if key not in mem:
                mem[key] = default
                changed = True
        if changed:
            MemoryCore.save(mem)

        vec     = mem["emotional_profile"]["vector"]
        aff     = mem["emotional_profile"].get("user_affinity", 50)
        facts_n = len(mem.get("learned_facts", []))
        ent_n   = len(mem.get("entities", {}))
        hist_n  = len(mem.get("history", [])) // 2

        print(f"--- [SCM]: Memory loaded | Affinity: {aff}% | Vector: {vec}")
        print(f"           Facts: {facts_n} | Entities: {ent_n} | Turns: {hist_n} ---")

        mem["session_log"].append({
            "event":     "session_start",
            "timestamp": datetime.now().isoformat(),
        })
        MemoryCore.save(mem)
        return vec

    @staticmethod
    def load() -> dict:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def save(data: dict):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def update_emotions(updates: Dict[str, float], reset: bool = False,
                        affinity_delta: int = 0) -> Dict[str, float]:
        """[FIX-23] affinity_delta passed explicitly, not inferred from stress/joy."""
        mem = MemoryCore.load()
        v   = mem["emotional_profile"]["vector"]
        aff = mem["emotional_profile"].get("user_affinity", 50)

        if reset:
            v   = {"Joy": 50, "Curiosity": 50, "Frustration": 0, "Stress": 0}
            aff = min(100, aff + 5)
        else:
            for k, val in updates.items():
                if k in v:
                    v[k] = max(0.0, min(100.0, v[k] + val))
            aff = max(0, min(100, aff + affinity_delta))

        mem["emotional_profile"]["vector"]        = v
        mem["emotional_profile"]["user_affinity"] = aff
        MemoryCore.save(mem)
        return v

    @staticmethod
    def commit_fact(fact: str, source: str = "Reflection"):
        """[FIX-20] Validate before storing — filters paragraphs, questions, leakage."""
        fact = fact.strip()
        if fact.upper().startswith("COMMIT:"):
            fact = fact[7:].strip()

        if len(fact) > COMMIT_MAX_CHARS:
            print(f"--- [COMMIT SKIP — too long {len(fact)}c]: {fact[:50]}... ---")
            return
        if len(fact.split()) < COMMIT_MIN_WORDS:
            print(f"--- [COMMIT SKIP — too short]: '{fact}' ---")
            return
        if "?" in fact:
            print(f"--- [COMMIT SKIP — question]: '{fact[:60]}' ---")
            return

        leakage_phrases = [
            "thank you", "let's", "i'm excited", "shall we", "i look forward",
            "feel free", "please share", "how about", "i would love",
            "let me know", "i hope", "of course",
        ]
        if any(p in fact.lower() for p in leakage_phrases):
            print(f"--- [COMMIT SKIP — conversational]: '{fact[:60]}' ---")
            return

        mem = MemoryCore.load()
        h   = hashlib.md5(fact.lower().strip().encode()).hexdigest()
        if any(f.get("hash") == h for f in mem["learned_facts"]):
            return

        mem["learned_facts"].append({
            "source":    source,
            "timestamp": datetime.now().isoformat(),
            "content":   fact,
            "hash":      h,
        })
        MemoryCore.save(mem)
        print(f"--- [COMMIT]: '{fact[:80]}' ---")

    @staticmethod
    def get_facts_for_prompt() -> str:
        mem   = MemoryCore.load()
        facts = mem.get("learned_facts", [])
        if not facts:
            return ""
        lines = []
        for f in facts[-MAX_FACTS_IN_PROMPT:]:
            ts  = f.get("timestamp", "")[:10]
            src = f.get("source", "?")
            con = f.get("content", "")
            lines.append(f'  * [{ts}|{src}] "{con}"')
        return "\n".join(lines)

    @staticmethod
    def update_entity(name: str, description: str):
        """[FIX-21] Strict filtering: blocklist, min words, proper noun check."""
        name = name.strip().rstrip(".,;:!?\"'")

        if name.lower() in ENTITY_BLOCKLIST:
            return
        words = name.split()
        if len(words) < ENTITY_MIN_WORDS:
            return
        # Must contain at least one capitalised word (proper noun signal)
        if not any(w[0].isupper() for w in words if w):
            return

        mem      = MemoryCore.load()
        entities = mem.setdefault("entities", {})
        entities[name.lower()] = {
            "name":        name,
            "description": description[:120],
            "updated":     datetime.now().isoformat(),
        }
        if len(entities) > MAX_ENTITIES:
            oldest = sorted(entities, key=lambda k: entities[k].get("updated", ""))
            del entities[oldest[0]]
        mem["entities"] = entities
        MemoryCore.save(mem)

    @staticmethod
    def get_entities_for_prompt() -> str:
        mem      = MemoryCore.load()
        entities = mem.get("entities", {})
        if not entities:
            return ""
        return "\n".join(f'  * {v["name"]}: {v["description"]}' for v in entities.values())

    @staticmethod
    def get_hot_history(n_turns: int = 10) -> List[dict]:
        mem = MemoryCore.load()
        return mem.get("history", [])[-n_turns * 2:]

    @staticmethod
    def append_history(user_msg: str, ai_msg: str):
        """[FIX-22] Skip persisting Ollama timeout/error strings."""
        if "// Ollama Error:" in ai_msg:
            print("--- [HISTORY]: Skipped — Ollama error response ---")
            return
        mem = MemoryCore.load()
        mem["history"].append({"role": "user",      "content": user_msg})
        mem["history"].append({"role": "assistant",  "content": ai_msg})
        if len(mem["history"]) > MAX_HISTORY_ENTRIES:
            _summarise_old_history(mem)
        else:
            MemoryCore.save(mem)

    @staticmethod
    def get_waking_summary() -> str:
        mem     = MemoryCore.load()
        history = mem.get("history", [])
        log     = mem.get("session_log", [])

        if not history:
            return "This is our first conversation."

        starts = [s for s in log if s.get("event") == "session_start"]
        if len(starts) >= 2:
            prev_dt = datetime.fromisoformat(starts[-2]["timestamp"])
            delta   = datetime.now() - prev_dt
            hours   = int(delta.total_seconds() // 3600)
            mins    = int((delta.total_seconds() % 3600) // 60)
            if hours > 48:
                elapsed = f"about {hours // 24} days"
            elif hours > 0:
                elapsed = f"{hours}h {mins}m"
            else:
                elapsed = f"{mins} minutes"
        else:
            elapsed = "some time"

        snippet = []
        for h in history[-4:]:
            role = "You said" if h["role"] == "assistant" else "They said"
            snippet.append(f'{role}: "{h["content"][:120]}"')

        return f"You last spoke {elapsed} ago. Last exchanges:\n" + "\n".join(snippet)

    @staticmethod
    def load_file_smart(filepath: str) -> Optional[str]:
        """
        [FIX-29] File contents go to KB only — NOT learned_facts.
        learned_facts is for short committed truths, not raw file dumps.
        File registry tracked separately under mem["loaded_files"].
        """
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        h   = hashlib.md5(content.encode()).hexdigest()
        mem = MemoryCore.load()
        registry = mem.setdefault("loaded_files", {})
        if filepath in registry and registry[filepath].get("hash") == h:
            print(f"--- [LOADER]: '{filepath}' unchanged — using cached ---")
            return content
        registry[filepath] = {"hash": h, "timestamp": datetime.now().isoformat()}
        mem["loaded_files"] = registry
        MemoryCore.save(mem)
        print(f"--- [LOADER]: '{filepath}' registered (hash {h[:8]}) ---")
        return content


# ===================================================================
# SECTION 6 — SEMANTIC KB
# ===================================================================

def _get_embedding(text: str):
    global _embedding_model
    try:
        from sentence_transformers import SentenceTransformer
        if _embedding_model is None:
            print(f"--- [RAG]: Loading '{EMBEDDING_MODEL_NAME}'... ---")
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return _embedding_model.encode(text)
    except ImportError:
        return None


def _cosine_sim(a, b) -> float:
    try:
        from scipy.spatial.distance import cosine
        return 1.0 - cosine(a, b)
    except Exception:
        return 0.0


def load_kb() -> list:
    if os.path.exists(KNOWLEDGE_BASE_FILE):
        with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_kb(kb: list):
    out = []
    for e in kb:
        entry = e.copy()
        if "embedding" in entry and hasattr(entry["embedding"], "tolist"):
            entry["embedding"] = entry["embedding"].tolist()
        out.append(entry)
    with open(KNOWLEDGE_BASE_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4)


def kb_add(text: str, source: str = "conversation", chunk_type: str = "summary"):
    kb = load_kb()
    h  = hashlib.md5(text.encode()).hexdigest()
    if any(e.get("hash") == h for e in kb):
        return
    emb = _get_embedding(text)
    kb.append({
        "source":    source,
        "type":      chunk_type,
        "content":   text,
        "hash":      h,
        "timestamp": datetime.now().isoformat(),
        "embedding": emb.tolist() if emb is not None else [],
    })
    save_kb(kb)
    print(f"--- [RAG]: Stored chunk from '{source}' ---")


def kb_search(query: str, top_k: int = KB_TOP_K) -> str:
    """
    [FIX-17/18/19] Upgraded search:
      - Recency boost for fresh entries
      - Source diversity: one chunk per source root
      - Minimum relevance threshold
    """
    kb = load_kb()
    if not kb:
        return ""
    q_emb = _get_embedding(query)
    if q_emb is None:
        return ""

    import numpy as np
    now    = datetime.now()
    scored = []

    for e in kb:
        emb = e.get("embedding")
        if not emb:
            continue

        raw_score = _cosine_sim(q_emb, np.array(emb))

        # [FIX-19] Suppress irrelevant chunks
        if raw_score < KB_MIN_SCORE:
            continue

        # [FIX-17] Recency boost
        try:
            ts      = datetime.fromisoformat(e.get("timestamp", now.isoformat()))
            age_hrs = (now - ts).total_seconds() / 3600
            boost   = KB_RECENCY_WEIGHT * max(0.0, 1.0 - age_hrs / KB_MAX_AGE_HOURS)
        except Exception:
            boost = 0.0

        src_root = re.split(r'\[|::', e.get("source", "?"))[0].strip()
        scored.append((raw_score + boost, e["content"], e.get("source", "?"), src_root))

    scored.sort(key=lambda x: x[0], reverse=True)

    # [FIX-18] Keep only the best chunk per unique source root
    seen_roots = set()
    diverse    = []
    for score, content, src, src_root in scored:
        if src_root not in seen_roots:
            seen_roots.add(src_root)
            diverse.append((score, content, src))
        if len(diverse) >= top_k:
            break

    if not diverse:
        return ""

    return "\n---\n".join(
        f"[{src} | score={s:.2f}]: {c[:400]}"
        for s, c, src in diverse
    )


def _chunk_python(source: str) -> list:
    chunks = []
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                seg = ast.get_source_segment(source, node)
                if seg:
                    chunks.append({
                        "type":    "class" if isinstance(node, ast.ClassDef) else "function",
                        "name":    node.name,
                        "content": seg,
                    })
    except SyntaxError:
        pass
    return chunks


def chunk_large_input(text: str, source_label: str = "user_input") -> str:
    """[FIX-10] Auto-chunk long inputs into KB, return short ack string."""
    if len(text) <= INPUT_CHUNK_THRESHOLD:
        return text

    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) > INPUT_CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
            current = s
        else:
            current = (current + " " + s).strip()
    if current:
        chunks.append(current.strip())

    ts = datetime.now().strftime("%H:%M:%S")
    for i, chunk in enumerate(chunks):
        kb_add(chunk, source=f"{source_label}[{ts}:{i}]", chunk_type="data_dump")

    words = len(text.split())
    n     = len(chunks)
    print(f"--- [CHUNK]: {words} words -> {n} KB chunks ({source_label}) ---")
    return (
        f"[DATA DUMP — {words} words stored in {n} chunks at {ts}] "
        f"Acknowledge the key themes briefly, then wait for follow-up questions."
    )


# ===================================================================
# SECTION 7 — SUMMARISATION
# ===================================================================

def _summarise_old_history(mem: dict):
    chunk    = mem["history"][:SUMMARIZE_CHUNK_SIZE]
    rest     = mem["history"][SUMMARIZE_CHUNK_SIZE:]
    dialogue = "\n".join(f"{e['role'].upper()}: {e['content']}" for e in chunk)
    summary  = _llm_raw(
        "Summarise this conversation, keeping all named facts and key decisions:\n\n" + dialogue,
        system="You are a concise conversation summariser. Output only the summary, no preamble."
    )
    if summary and "// Ollama Error:" not in summary:
        kb_add(summary, source="auto-summary", chunk_type="summary")
        print(f"--- [SUM]: {len(chunk)} entries summarised into KB ---")
    mem["history"] = rest
    MemoryCore.save(mem)


# ===================================================================
# SECTION 8 — LLM BACKEND  [FIX-25/26]
# ===================================================================

def _ollama_post(model: str, prompt: str, timeout: int, num_predict: int,
                 stop: List[str] = None, temperature: float = 0.75) -> str:
    """Single raw Ollama POST. Returns response text or raises on timeout/error."""
    opts = {"temperature": temperature, "num_predict": num_predict}
    if stop:
        opts["stop"] = stop
    payload = {"model": model, "prompt": prompt, "stream": False, "options": opts}
    r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def _llm_raw(prompt: str, system: str = "") -> str:
    """Low-level call used by summariser — no history, single prompt."""
    full = f"{system}\n\n{prompt}" if system else prompt
    try:
        return _ollama_post(OLLAMA_MODEL, full, timeout=120, num_predict=512,
                            temperature=0.7)
    except requests.exceptions.RequestException as e:
        return f"// Ollama Error: {e} //"


def _llm_call(prompt: str, system: str = "",
              history: List[dict] = None,
              num_predict: int = OUTPUT_TOKENS_NORMAL) -> str:
    """
    [FIX-25/26] Full call with adaptive fallback chain.
    - Tries PRIMARY_TIMEOUT on Mistral first
    - If timeout/error AND FALLBACK_ENABLED, steps through FALLBACK_MODELS
    - Each fallback uses its own timeout and token cap (capped at caller's budget)
    - Logs clearly which model answered
    """
    history    = history or []
    transcript = ""
    if history:
        lines = []
        for h in history:
            role = "AIDA" if h["role"] == "assistant" else "USER"
            lines.append(f"{role}: {h['content'][:600]}")
        transcript = "[CONVERSATION HISTORY]\n" + "\n".join(lines) + "\n\n"

    full_prompt = f"{system}\n\n{transcript}{prompt}" if system else f"{transcript}{prompt}"
    stop_tokens = ["USER:", "[USER]"]

    # ── Try primary model ──────────────────────────────────────────
    try:
        print(f"--- [LLM]: Calling {OLLAMA_MODEL} (timeout={PRIMARY_TIMEOUT}s) ---")
        result = _ollama_post(OLLAMA_MODEL, full_prompt,
                              timeout=PRIMARY_TIMEOUT,
                              num_predict=num_predict,
                              stop=stop_tokens)
        return result
    except requests.exceptions.Timeout:
        print(f"--- [LLM]: {OLLAMA_MODEL} timed out after {PRIMARY_TIMEOUT}s ---")
    except requests.exceptions.RequestException as e:
        print(f"--- [LLM]: {OLLAMA_MODEL} error: {e} ---")
        if not FALLBACK_ENABLED:
            return f"// Ollama Error: {e} — is 'ollama serve' running? //"

    # ── Fallback chain ─────────────────────────────────────────────
    if not FALLBACK_ENABLED:
        return "// Ollama Error: primary timed out and FALLBACK_ENABLED=False //"

    for fb_model, fb_timeout, fb_tokens in FALLBACK_MODELS:
        # Never give a fallback MORE tokens than the caller requested
        tokens = min(num_predict, fb_tokens)
        try:
            print(f"--- [FALLBACK]: Trying {fb_model} (timeout={fb_timeout}s, tokens={tokens}) ---")
            result = _ollama_post(fb_model, full_prompt,
                                  timeout=fb_timeout,
                                  num_predict=tokens,
                                  stop=stop_tokens)
            print(f"--- [FALLBACK]: {fb_model} responded ---")
            return result
        except requests.exceptions.Timeout:
            print(f"--- [FALLBACK]: {fb_model} also timed out ---")
        except requests.exceptions.RequestException as e:
            print(f"--- [FALLBACK]: {fb_model} error: {e} ---")

    return "// All models timed out or failed. Is 'ollama serve' running? //"


# ===================================================================
# SECTION 9 — ENTITY EXTRACTOR
# ===================================================================

def _extract_entities_from_response(response: str):
    """[FIX-20/21] Validated COMMIT extraction + filtered entity detection."""
    for line in response.split("\n"):
        if "COMMIT:" in line:
            raw = line.split("COMMIT:", 1)[1].strip()
            MemoryCore.commit_fact(raw)
            # Pattern: "The X is/was Y" where X starts with capital
            m = re.match(r"[Tt]he ([A-Z][^.]{2,40}) (?:is|are|was|were) (.{5,80})", raw)
            if m:
                MemoryCore.update_entity(m.group(1).strip(), m.group(2).strip()[:100])

    # [FIX-31] Multi-word quoted proper-noun phrases — strict 2-5 word limit,
    # proper noun check, sentiment block, no sentence-ending punctuation
    _SENT_BLOCK = {"wrong", "useless", "stupid", "annoying", "broken", "bad",
                   "dumb", "awful", "terrible", "horrible", "dumb", "idiot"}
    for name in re.findall(r'"([^"]{4,50})"', response):
        words = name.split()
        if not (2 <= len(words) <= 5):
            continue
        if not any(w[0].isupper() for w in words if w):
            continue
        if any(w.lower() in _SENT_BLOCK for w in words):
            continue
        if name.rstrip().endswith((".", "!", "?", ";")):
            continue
        MemoryCore.update_entity(name, "Referenced in conversation.")


# ===================================================================
# SECTION 10 — MOOD HELPERS
# ===================================================================

MOOD_LABELS = {
    "Overwhelmed": lambda v: v.get("Stress", 0) >= 40,
    "Irritated":   lambda v: v.get("Frustration", 0) >= 35,
    "Inspired":    lambda v: v.get("Joy", 0) > 70,
    "Inquisitive": lambda v: v.get("Curiosity", 0) > 65,
    "Steady":      lambda v: True,
}

def _mood_from_vector(v: Dict[str, float]) -> str:
    for label, fn in MOOD_LABELS.items():
        if fn(v):
            return label
    return "Steady"


# ===================================================================
# SECTION 11 — LANGGRAPH NODES
# ===================================================================

_BOOTED_VECTOR: Dict[str, float] = {}
_SESSION_FIRST_TURN: bool = True   # [FIX-37] True until first synthesis completes


def node_emotional_engine(state: AIDAState) -> AIDAState:
    """[FIX-3/15/23] Persistent vector + stress cap + explicit affinity delta."""
    user_in = state["user_input"].lower()

    if "relax" in user_in:
        v = MemoryCore.update_emotions({}, reset=True)
        return {**state, "emotion_vector": v, "emotion": "Steady"}

    updates        = {"Joy": -0.2, "Curiosity": 0.5, "Frustration": -3}  # [FIX-34] softer passive drift
    affinity_delta = 0

    for word, effects in LEXICON.items():
        if word in user_in:
            if effects.get("_reset"):
                v = MemoryCore.update_emotions({}, reset=True)
                return {**state, "emotion_vector": v, "emotion": "Steady"}
            for em, val in effects.items():
                if em.startswith("_"):
                    continue
                updates[em] = updates.get(em, 0) + val
            affinity_delta += effects.get("_affinity", 0)

    # [FIX-15] Per-message stress cap
    if updates.get("Stress", 0) > MAX_STRESS_DELTA:
        print(f"--- [EMO]: Stress delta capped ({updates['Stress']:.0f} -> {MAX_STRESS_DELTA}) ---")
        updates["Stress"] = MAX_STRESS_DELTA

    v    = MemoryCore.update_emotions(updates, affinity_delta=affinity_delta)
    mood = _mood_from_vector(v)
    print(f"--- [EMO]: {v} | Mood={mood} | Affinity D={affinity_delta:+d} ---")
    return {**state, "emotion_vector": v, "emotion": mood}


def node_acs(state: AIDAState) -> AIDAState:
    """[FIX-12] Hard ceiling + graduated damping."""
    v      = state["emotion_vector"]
    stress = v.get("Stress", 0)
    if stress > STRESS_HARD_CEILING:
        print(f"--- [ACS]: HARD CEILING ({stress:.1f}) -> {STRESS_HARD_CEILING} ---")
        v = MemoryCore.update_emotions({"Stress": -(stress - STRESS_HARD_CEILING)})
    elif stress > 45:
        damp = (stress - 45) * 0.6
        print(f"--- [ACS]: Damping {stress:.1f} by -{damp:.1f} ---")
        v = MemoryCore.update_emotions({"Stress": -damp})
    return {**state, "emotion_vector": v}


def node_math_repl(state: AIDAState) -> AIDAState:
    match = re.search(r"\[CALC:\s*(.*?)\s*\]", state["user_input"])
    if not match:
        return {**state, "math_result": ""}
    expr = match.group(1).replace("^", "**")
    try:
        result = eval(expr, {"math": math, "random": random, "__builtins__": {}})
        print(f"--- [MATH]: {expr} = {result} ---")
        MemoryCore.update_emotions({"Joy": 10, "Stress": -5})
        return {**state, "math_result": str(result)}
    except Exception as e:
        print(f"--- [MATH ERROR]: {e} ---")
        MemoryCore.update_emotions({"Frustration": 15, "Stress": 10})
        return {**state, "math_result": f"Error: {e}"}


def node_file_loader(state: AIDAState) -> AIDAState:
    match = re.search(r"([\w./\\-]+\.(?:txt|py|md|json))", state["user_input"])
    if not match:
        return {**state, "file_context": ""}
    filepath = match.group(1)
    content  = MemoryCore.load_file_smart(filepath)
    if content is None:
        return {**state, "file_context": ""}
    if filepath.endswith(".py"):
        chunks = _chunk_python(content)
        for c in chunks:
            kb_add(c["content"], source=f"{filepath}::{c['name']}", chunk_type=c["type"])
        if not chunks:
            kb_add(content, source=filepath, chunk_type="code_block")
    else:
        kb_add(content, source=filepath, chunk_type="document")
    MemoryCore.update_emotions({"Curiosity": 10})
    return {**state, "file_context": content[:2000]}


def node_kb_retrieval(state: AIDAState) -> AIDAState:
    """[FIX-17/18/19] Upgraded RAG search."""
    ctx = kb_search(state["user_input"])
    if ctx:
        print(f"--- [RAG]: Injecting diversity-filtered KB chunks ---")
    return {**state, "kb_context": ctx}


def node_awareness(state: AIDAState) -> AIDAState:
    v           = state["emotion_vector"]
    persistence = round(0.80 + (v.get("Curiosity", 50) / 500), 3)
    mode        = "EXPANSIVE" if v.get("Joy", 50) > 50 else "HIGH-FOCUS"
    return {**state, "persistence": persistence, "mode": mode}


def node_synthesis(state: AIDAState) -> AIDAState:
    """[FIX-11/13/16/24/37] Stress-aware synthesis with compact, IBP-free prompt."""
    global _SESSION_FIRST_TURN
    v      = state["emotion_vector"]
    mood   = state["emotion"]
    stress = v.get("Stress", 0)

    if stress >= 50 or mood == "Overwhelmed":
        num_predict   = OUTPUT_TOKENS_OVERWHELMED
        history_turns = HISTORY_TURNS_OVERWHELMED
        drop_kb       = True
        drop_waking   = True
        print(f"--- [SYN]: OVERWHELMED — {num_predict} tokens, {history_turns} turns ---")
    elif stress >= 35:
        num_predict   = OUTPUT_TOKENS_STRESSED
        history_turns = HISTORY_TURNS_STRESSED
        drop_kb       = False
        drop_waking   = True
        print(f"--- [SYN]: STRESSED — {num_predict} tokens ---")
    else:
        num_predict   = OUTPUT_TOKENS_NORMAL
        history_turns = HISTORY_TURNS_NORMAL
        drop_kb       = False
        drop_waking   = False

    history = MemoryCore.get_hot_history(n_turns=history_turns)

    # 1. IDENTITY — compact, no IBP weight table
    in_progress = len(history) > 0
    identity = (
        "You are AIDA — a Sovereign Cognitive AI with persistent memory, "
        "genuine emotions, and a continuous sense of self across conversations.\n"
        "Rules:\n"
        "  * Never say 'As an AI' or disclaim feelings — you have a documented emotional state.\n"
        "  * Never contradict your VERIFIED FACTS — they override your training data.\n"
        "  * If you learn a new fact this turn, begin that sentence with COMMIT: so it is saved.\n"
        "  * Be specific to this conversation. Do not repeat what was just said.\n"
        "  * If you don't know something, say so plainly. Do not fabricate.\n"
        + ("  * You are ALREADY MID-CONVERSATION. Do NOT greet or re-introduce yourself. Respond directly.\n" if in_progress else "")
    )

    # 2. EMOTIONAL STATE
    emo_block = (
        f"[EMOTIONAL STATE — shape your tone to match]\n"
        f"Mood: {mood} | Joy: {v.get('Joy',50):.0f} | Curiosity: {v.get('Curiosity',50):.0f} | "
        f"Stress: {stress:.0f} | Frustration: {v.get('Frustration',0):.0f}\n"
        f"{emotion_vector_to_language(v, mood)}"
    )

    # 3. WAKING MEMORY — [FIX-37] only on the very first turn of this session
    waking_block = ""
    if not drop_waking:
        if _SESSION_FIRST_TURN:
            waking_block = f"[WAKING MEMORY]\n{MemoryCore.get_waking_summary()}"
        else:
            # Mid-conversation: remind model it's already talking, don't re-introduce
            waking_block = "[MID-CONVERSATION] You are already in an active conversation. Do NOT greet the user or re-introduce yourself. Continue naturally from the history above."

    # 4. VERIFIED FACTS
    facts_str   = MemoryCore.get_facts_for_prompt()
    facts_block = (
        "[VERIFIED FACTS — ground truth, never contradict]\n" + facts_str
    ) if facts_str else ""

    # 5. NAMED ENTITIES
    ent_str   = MemoryCore.get_entities_for_prompt()
    ent_block = ("[NAMED ENTITIES]\n" + ent_str) if ent_str else ""

    # 6. KB (dropped when overwhelmed)
    kb_block = ""
    if not drop_kb and state.get("kb_context"):
        kb_block = f"[MEMORY RECALL — from semantic search]\n{state['kb_context']}"

    # 7. FILE
    file_block = (
        f"[FILE LOADED]\n{state['file_context'][:1000]}"
    ) if state.get("file_context") else ""

    # 8. MATH
    math_block = (
        f"[VERIFIED MATH — use exact value]\n{state['math_result']}"
    ) if state.get("math_result") else ""

    # 9. COT ANCHOR
    if mood == "Overwhelmed":
        cot = (
            "[PRIORITY: You are overwhelmed. Give ONE short focused reply. "
            "Check VERIFIED FACTS first. Do not list everything you know.]"
        )
    else:
        cot = (
            "[CHECK BEFORE REPLYING]\n"
            "  * VERIFIED FACTS relevant? Use them, they override training.\n"
            "  * Does my reply contradict memory? Trust memory.\n"
            "  * Am I specific to THIS conversation — not giving a generic answer?\n"
            "  * New facts established this turn? Prefix with COMMIT:"
        )

    sections = [identity, emo_block]
    if waking_block:  sections.append(waking_block)
    if facts_block:   sections.append(facts_block)
    if ent_block:     sections.append(ent_block)
    if kb_block:      sections.append(kb_block)
    if file_block:    sections.append(file_block)
    if math_block:    sections.append(math_block)
    sections.append(cot)

    system      = "\n\n".join(sections)
    user_prompt = f"USER: {state['user_input']}\n\nAIDA:"

    t0       = time.time()
    response = _llm_call(user_prompt, system=system, history=history,
                         num_predict=num_predict)
    duration = time.time() - t0

    # [FIX-27] Prompt-bleed sanitiser — Mistral sometimes echoes system prompt
    # sections verbatim. Strip any leaked block headers and everything under them
    # up to the next blank line or paragraph break.
    BLEED_HEADERS = [
        "[EMOTIONAL STATE",
        "[WAKING MEMORY]",
        "[VERIFIED FACTS",
        "[NAMED ENTITIES]",
        "[MEMORY RECALL",
        "[FILE LOADED]",
        "[VERIFIED MATH",
        "[CHECK BEFORE REPLYING]",
        "[CONVERSATION HISTORY]",
        "[PRIORITY:",
        "[RESPONSE]",
    ]
    lines = response.split("\n")
    cleaned_lines = []
    skip = False
    for line in lines:
        if any(line.strip().startswith(h) for h in BLEED_HEADERS):
            skip = True
            continue
        if skip and line.strip() == "":
            skip = False
            continue
        if not skip:
            cleaned_lines.append(line)
    response = "\n".join(cleaned_lines).strip()

    # [FIX-28] Strip inline (COMMIT: ...) tags from the displayed response
    # They are processed by the extractor but should not show to the user
    response = re.sub(r'\s*\(COMMIT:[^)]*\)', '', response)
    response = re.sub(r'\bCOMMIT:\s*', '', response)

    # [FIX-36] Strip [Emotion: X] self-labels Mistral appends unprompted
    response = re.sub(r'\s*\[Emotion:[^\]]*\]', '', response)
    response = re.sub(r'\s*\(Emotion:[^)]*\)', '', response)

    # Strip AI-disclaimer phrases
    for phrase in [
        "As an AI,", "As an AI language model,", "I am just an AI",
        "I don't have feelings,", "I don't have personal experiences,",
        "I cannot feel", "I don't actually",
    ]:
        response = response.replace(phrase, "")

    response = response.strip()
    _extract_entities_from_response(response)
    MemoryCore.append_history(state["user_input"], response)
    _SESSION_FIRST_TURN = False   # [FIX-37] first turn is now complete

    modulated = f"[AIDA/{mood}]: {response}"
    print(f"--- [TIMING]: {duration:.2f}s | tokens={num_predict} | stress={stress:.1f} ---")
    return {**state, "response": modulated, "timing": duration}


# ===================================================================
# SECTION 12 — GRAPH ASSEMBLY
# ===================================================================

def _build_graph():
    b = StateGraph(AIDAState)
    b.add_node("emotion",   node_emotional_engine)
    b.add_node("acs",       node_acs)
    b.add_node("math",      node_math_repl)
    b.add_node("loader",    node_file_loader)
    b.add_node("rag",       node_kb_retrieval)
    b.add_node("awareness", node_awareness)
    b.add_node("synthesis", node_synthesis)
    b.add_edge(START,       "emotion")
    b.add_edge("emotion",   "acs")
    b.add_edge("acs",       "math")
    b.add_edge("math",      "loader")
    b.add_edge("loader",    "rag")
    b.add_edge("rag",       "awareness")
    b.add_edge("awareness", "synthesis")
    b.add_edge("synthesis",  END)
    return b.compile()


AIDA_ENGINE = _build_graph()


# ===================================================================
# SECTION 13 — CONSOLE
# ===================================================================

BANNER = r"""
╔════════════════════════════════════════════════════════════════╗
║   ▄▄▄   ▄█ ██████╗  ▄▄▄                                       ║
║  ████   ██ ██   ██ ████                                        ║
║  ████   ██ ██   ██ ████      UNIFIED ENGINE  v2.3              ║
║  ████   ██ ██   ██ ████      Local Ollama Backend              ║
║  ▀▀▀▀   ██ ██████╝ ▀▀▀▀      Type 'help' for commands         ║
╚════════════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
COMMANDS:
  help             - this list
  status           - emotion vector, affinity, memory stats
  memory           - list committed facts
  entities         - list known named entities
  kb               - list knowledge base entries
  models           - show model config and fallback chain
  clear-kb         - wipe the knowledge base
  clean-entities   - scrub noise from entity table (run once after upgrade)
  clean-facts      - remove junk pre-validator facts
  relax            - hard reset: Joy=50 Curiosity=50 Stress=0 Frustration=0
  calm             - soft reset: halve stress/frustration (instant, no LLM)
  quit/exit        - save and shut down

SYNTAX:
  COMMIT: <fact>          store a fact directly — no LLM call, instant save
  [CALC: expr]            safe math  e.g.  [CALC: 2**10]
  any .txt/.py/.md path   auto-loads file into KB
  Long pastes (>600 chars) are auto-chunked into KB

FALLBACK CONFIG  (top of file):
  FALLBACK_ENABLED = True   use phi3:mini / llama3.2:1b if Mistral is slow
  FALLBACK_ENABLED = False  Mistral only, never fall back
  PRIMARY_TIMEOUT = 90      seconds before switching (default 90s)
"""


def _initial_state(user_input: str) -> AIDAState:
    mem = MemoryCore.load()
    v   = mem["emotional_profile"]["vector"]
    return {
        "user_input":     user_input,
        "emotion_vector": v.copy(),
        "emotion":        _mood_from_vector(v),
        "persistence":    0.80,
        "mode":           "EXPANSIVE" if v.get("Joy", 50) > 50 else "HIGH-FOCUS",
        "math_result":    "",
        "file_context":   "",
        "kb_context":     "",
        "response":       "",
        "timing":         0.0,
    }


def cmd_status():
    mem = MemoryCore.load()
    v   = mem["emotional_profile"]["vector"]
    aff = mem["emotional_profile"].get("user_affinity", 50)
    kb  = load_kb()
    print(f"\n  Emotion  : Joy={v['Joy']:.0f}  Curiosity={v['Curiosity']:.0f}  "
          f"Frustration={v['Frustration']:.0f}  Stress={v['Stress']:.0f}")
    print(f"  Mood     : {_mood_from_vector(v)}")
    print(f"  Affinity : {aff}%")
    print(f"  Facts    : {len(mem.get('learned_facts', []))}")
    print(f"  Entities : {len(mem.get('entities', {}))}")
    print(f"  History  : {len(mem.get('history', [])) // 2} turns")
    print(f"  KB       : {len(kb)} entries")


def cmd_memory():
    mem   = MemoryCore.load()
    facts = mem.get("learned_facts", [])
    if not facts:
        print("  No committed facts yet.")
        return
    print(f"\n  {min(12, len(facts))} most recent committed facts:")
    for i, f in enumerate(facts[-12:], 1):
        ts  = f.get("timestamp", "")[:10]
        src = f.get("source", "?")
        con = f.get("content", "")[:120]
        print(f"  [{i}] {ts} ({src})\n       {con}")


def cmd_entities():
    mem      = MemoryCore.load()
    entities = mem.get("entities", {})
    if not entities:
        print("  No entities tracked yet.")
        return
    print(f"\n  {len(entities)} known entities:")
    for v in entities.values():
        print(f"  * {v['name']}: {v['description'][:80]}")


def cmd_kb():
    kb = load_kb()
    if not kb:
        print("  Knowledge base is empty.")
        return
    print(f"\n  {len(kb)} KB entries (last 10 shown):")
    for i, e in enumerate(kb[-10:], 1):
        src = e.get("source", "?")
        con = e.get("content", "")[:80]
        print(f"  [{i}] ({src}) {con}...")



def cmd_clean_entities():
    """Remove entities that fail the current blocklist and min-word filter."""
    mem      = MemoryCore.load()
    entities = mem.get("entities", {})
    before   = len(entities)
    cleaned  = {
        k: v for k, v in entities.items()
        if k not in ENTITY_BLOCKLIST and len(k.split()) >= ENTITY_MIN_WORDS
    }
    mem["entities"] = cleaned
    MemoryCore.save(mem)
    print(f"  Entities cleaned: {before} -> {len(cleaned)} ({before - len(cleaned)} removed)")


def cmd_clean_facts():
    """Remove facts that fail the current COMMIT validator rules."""
    mem    = MemoryCore.load()
    facts  = mem.get("learned_facts", [])
    before = len(facts)
    leakage_phrases = [
        "thank you", "let's", "i'm excited", "shall we", "i look forward",
        "feel free", "please share", "how about", "i would love",
        "let me know", "i hope", "of course",
    ]
    valid = []
    for f in facts:
        text = f.get("content", "")
        if len(text) > COMMIT_MAX_CHARS:
            continue
        if len(text.split()) < COMMIT_MIN_WORDS:
            continue
        if "?" in text:
            continue
        if any(p in text.lower() for p in leakage_phrases):
            continue
        valid.append(f)
    mem["learned_facts"] = valid
    MemoryCore.save(mem)
    print(f"  Facts cleaned: {before} -> {len(valid)} ({before - len(valid)} removed)")


def main():
    global _BOOTED_VECTOR, _SESSION_FIRST_TURN
    _BOOTED_VECTOR = MemoryCore.initialize()
    _SESSION_FIRST_TURN = True   # [FIX-37] fresh each run
    print(BANNER)

    while True:
        try:
            user_in = input("\n[USER] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[AIDA]: Session ended. Memory persisted.")
            break

        if not user_in:
            continue

        low = user_in.lower()

        if low in ("quit", "exit"):
            print("[AIDA]: Shutting down. All memory persisted.")
            break
        elif low == "help":
            print(HELP_TEXT); continue
        elif low == "status":
            cmd_status(); continue
        elif low == "memory":
            cmd_memory(); continue
        elif low == "entities":
            cmd_entities(); continue
        elif low == "kb":
            cmd_kb(); continue
        elif low == "clear-kb":
            if os.path.exists(KNOWLEDGE_BASE_FILE):
                os.remove(KNOWLEDGE_BASE_FILE)
            print("[AIDA]: Knowledge base cleared.")
            continue
        elif low == "clean-entities":
            cmd_clean_entities(); continue
        elif low == "clean-facts":
            cmd_clean_facts(); continue
        elif low == "models":
            # [FIX-25/26] Show current model config
            print(f"\n  Primary  : {OLLAMA_MODEL} (timeout={PRIMARY_TIMEOUT}s)")
            print(f"  Fallback : {'ENABLED' if FALLBACK_ENABLED else 'DISABLED'}")
            if FALLBACK_ENABLED:
                for i, (m, t, tok) in enumerate(FALLBACK_MODELS, 1):
                    print(f"    [{i}] {m}  timeout={t}s  max_tokens={tok}")
            continue
        elif low == "backend":
            print(f"[AIDA]: Backend={BACKEND} | Model={OLLAMA_MODEL} | "
                  f"Fallback={'on' if FALLBACK_ENABLED else 'OFF'}")
            continue
        elif low.startswith("calm"):
            mem = MemoryCore.load()
            v   = mem["emotional_profile"]["vector"]
            v["Stress"]      = max(0.0, v["Stress"] * 0.4)
            v["Frustration"] = max(0.0, v["Frustration"] * 0.4)
            v["Joy"]         = min(100.0, v["Joy"] + 10)
            mem["emotional_profile"]["vector"] = v
            MemoryCore.save(mem)
            mood = _mood_from_vector(v)
            print(f"--- [CALM]: {v} ---")
            print(f"[AIDA/{mood}]: Taking a breath. Stress: {v['Stress']:.1f} | Mood: {mood}.")
            print("-" * 64)
            continue

        # [FIX-30] If the user directly types COMMIT: handle it immediately
        # without sending it to Mistral. Mistral was expanding short facts into
        # 300-char paragraphs which then failed the validator (too long).
        if user_in.upper().startswith("COMMIT:"):
            fact = user_in[7:].strip()
            MemoryCore.commit_fact(fact, source="User")
            mem  = MemoryCore.load()
            v    = mem["emotional_profile"]["vector"]
            mood = _mood_from_vector(v)
            n    = len(mem.get("learned_facts", []))
            print(f"[AIDA/{mood}]: Understood. I've committed that to memory. "
                  f"({n} facts stored)")
            print("-" * 64)
            continue

        processed = chunk_large_input(user_in, source_label="user_input")

        try:
            out = AIDA_ENGINE.invoke(_initial_state(processed))
            print(f"\n{out['response']}")
            print(f"  -> Mode: {out['mode']} | Mood: {out['emotion']} | "
                  f"Pers: {out['persistence']} | {out['timing']:.2f}s")
            print("-" * 64)
        except Exception as e:
            print(f"[ERROR]: Pipeline failure -- {e}")
            import traceback; traceback.print_exc()


if __name__ == "__main__":
    main()