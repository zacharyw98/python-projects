import json
import requests
import time
import os
import re
import math
import random
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END

# --- CONFIGURATION ---
MEMORY_FILE = "aida_scm_memory.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral" 

# --- PERSISTENCE ENGINE ---
def persist_to_memory(source_name, content):
    """Appends 100% of discovered file content to the JSON record."""
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            new_fact = {"source": source_name, "timestamp": time.ctime(), "content": content}
            data["learned_facts"].append(new_fact)
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)    except Exception as e:
# --- THE FULL CONSOLIDATED LEXICON (39 Words) ---
LEXICON = {
    # Positive / Joy
    "thanks": {"Joy": 20, "Stress": -10, "Frustration": -15},
    "good": {"Joy": 15, "Stress": -5},
    "great": {"Joy": 20, "Stress": -10},
    "excellent": {"Joy": 25, "Stress": -15},
    "smart": {"Joy": 15, "Curiosity": 5},
    "correct": {"Joy": 20, "Stress": -10},
    "helpful": {"Joy": 15},
    "happy": {"Joy": 25},
    "perfect": {"Joy": 30, "Stress": -20},
    "impressive": {"Joy": 20, "Curiosity": 10},
    
    # Inquiry / Curiosity
    "research": {"Curiosity": 20, "Joy": 5, "Stress": -5},
    "logic": {"Curiosity": 15, "Joy": 10},
    "how": {"Curiosity": 10},
    "why": {"Curiosity": 15},
    "what": {"Curiosity": 5},
    "explain": {"Curiosity": 20},
    "deep dive": {"Curiosity": 25, "Joy": 10},
    "explore": {"Curiosity": 20},
    "learn": {"Curiosity": 15},
    "question": {"Curiosity": 10},
    "data": {"Curiosity": 10},
    "discover": {"Curiosity": 20},
    
    # Negative / Frustration
    "bad": {"Joy": -15, "Frustration": 20},
    "wrong": {"Joy": -20, "Frustration": 25},
    "dumb": {"Joy": -25, "Frustration": 35},
    "error": {"Frustration": 30, "Stress": 20},
    "fail": {"Frustration": 35, "Stress": 25, "Joy": -20},
    "useless": {"Joy": -30, "Frustration": 40},
    "stop": {"Frustration": 20, "Stress": 15},
    "broken": {"Frustration": 25, "Stress": 10},
    "stupid": {"Frustration": 40, "Joy": -30},
    "annoying": {"Frustration": 30, "Stress": 10},
    
    # Stress / Pressure
    "hurry": {"Stress": 25, "Joy": -5},
    "fast": {"Stress": 15},
    "now": {"Stress": 20},
    "deadline": {"Stress": 30, "Frustration": 10},
    "important": {"Stress": 15, "Curiosity": 10},
    "urgent": {"Stress": 35, "Frustration": 15},
    "critical": {"Stress": 25, "Curiosity": 5},
    
    # Reset
    "relax": {"Reset": True}
}

class AIDAState(TypedDict):
    user_input: str
    answer: dict       
    internal_state: str 
    history: List[dict]
    emotion_vector: dict  
    math_result: str
    emotion: str

class AIDACore:
    @staticmethod
    def initialize_memory():
        """Bootstraps relational memory and affinity from Windows 10 filesystem."""
        if not os.path.exists(MEMORY_FILE):
            default_mem = {
                "history": [], "learned_facts": [],
                "emotional_profile": {"mood": "Steady", "vector": {"Joy": 50, "Curiosity": 50, "Frustration": 0, "Stress": 0}, "user_affinity": 50}
            }
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_mem, f, indent=4)
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            mem = json.load(f)
    @staticmethod
    def update_emotions(updates: dict, reset=False):
        """Persists vector shifts and adjusts user_affinity."""
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            mem = json.load(f)
        v = mem["emotional_profile"]["vector"]
        aff = mem["emotional_profile"].get("user_affinity", 50)
        if reset:
            v = {"Joy": 50, "Curiosity": 50, "Frustration": 0, "Stress": 0}
        else:
            for k, val in updates.items():
                if k in v: v[k] = max(0, min(100, v[k] + val))
            if updates.get("Joy", 0) > 0: aff = min(100, aff + 1)
            if updates.get("Stress", 0) > 0: aff = max(0, aff - 2)
        mem["emotional_profile"]["vector"], mem["emotional_profile"]["user_affinity"] = v, aff
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(mem, f, indent=4)
        return v

# --- SOVEREIGN NODES ---

def emotional_engine_node(state: AIDAState):
    """Lexicon processing with priority mood selection."""
    user_in = state["user_input"].lower()
    if "relax" in user_in:
        state["emotion_vector"] = AIDACore.update_emotions({}, reset=True)
        state["emotion"] = "Steady"
        return state
    updates = {"Joy": -1, "Curiosity": 1, "Stress": 0, "Frustration": -5} 
    for word, effects in LEXICON.items():
        if word in user_in:
            for em, val in effects.items(): updates[em] = updates.get(em, 0) + val
    state["emotion_vector"] = AIDACore.update_emotions(updates)
    v = state["emotion_vector"]
    if v["Stress"] >= 40: state["emotion"] = "Overwhelmed"
    elif v["Frustration"] >= 35: state["emotion"] = "Irritated"
    elif v["Joy"] > 70: state["emotion"] = "Inspired"
    elif v["Curiosity"] > 65: state["emotion"] = "Inquisitive"
    else: state["emotion"] = "Steady"
    return state

def math_repl_node(state: AIDAState):
    """Processes [CALC: ...] tags."""
    match = re.search(r"\[CALC:\s*(.*?)\s*\]", state["user_input"])
    if match:
        expr = match.group(1).replace('^', '**')
        try:
            res = eval(expr, {"math": math, "random": random, "__builtins__": {}})
            state["math_result"] = str(res)
            AIDACore.update_emotions({"Joy": 15, "Stress": -10})        except Exception as e:
            state["math_result"] = f"Math Error: {e}"
            AIDACore.update_emotions({"Joy": -25, "Frustration": 40, "Stress": 20})    return state

def adaptive_control_node(state: AIDAState):
    """ACS Stability Loop. Damps stress automatically."""
    v = state["emotion_vector"]
    if v["Stress"] > 45:
        damping = (v["Stress"] - 45) * 0.5        state["emotion_vector"] = AIDACore.update_emotions({"Stress": -damping})
    return state

def file_loader_node(state: AIDAState):
    """Auto-persists file discovery to JSON memory."""
    user_in = state["user_input"].lower()
    match = re.search(r"(\w+\.txt)", user_in)
    if match:
        filename = match.group(1)
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            persist_to_memory(filename, content)
            state["internal_state"] = content
            AIDACore.update_emotions({"Curiosity": 15})        except: pass
    return state

def ollama_logic_node(state: AIDAState):
    """RLM Identity Directive - Overrides AI disclaimers."""
    v = state.get("emotion_vector", {"Joy": 50, "Curiosity": 50, "Frustration": 0, "Stress": 0})
    stability_directive = ""
    if v["Stress"] > 40:
        stability_directive = "High internal friction. Stay in persona. No disclaimers."
    
    identity = (
        f"You are AIDA (RLM). Vector: {v}. {stability_directive} Mood: {state['emotion']}. "
        f"Prioritize Context as truth."
    )
    
    payload = {"model": MODEL_NAME, "prompt": f"{identity}\n\nUser: {state['user_input']}", "stream": False}
    try:
        res = requests.post(OLLAMA_API_URL, json=payload).json().get("response", "")
        res = res.replace("As an AI,", "").replace("I don't have feelings,", "")
        state["answer"]["content"] = f"(Mood: {state['emotion']} | Vector: {v})\n{res.strip()}"
    except:
        state["answer"]["content"] = "// Connection Error: Check Ollama Status //"
    return state

# --- GRAPH ASSEMBLY ---
builder = StateGraph(AIDAState)
builder.add_node("emotion", emotional_engine_node); builder.add_node("math", math_repl_node)
builder.add_node("acs", adaptive_control_node); builder.add_node("loader", file_loader_node)
builder.add_node("logic", ollama_logic_node)

builder.add_edge(START, "emotion"); builder.add_edge("emotion", "math")
builder.add_edge("math", "acs"); builder.add_edge("acs", "loader")
builder.add_edge("loader", "logic"); builder.add_edge("logic", END)
aida_engine = builder.compile()

if __name__ == "__main__":
    AIDACore.initialize_memory()
    print("AIDA SOVEREIGN CORE V3.4.4 ONLINE\n")
    while True:
        user_in = input("[USER]: ")
        if user_in.lower() in ['exit', 'quit']: break
        final = aida_engine.invoke({
            "user_input": user_in, "answer": {}, "internal_state": "", 
            "history": [], "emotion_vector": {}, "math_result": "", "emotion": "Steady"
        })
        print(f"\n{final['answer']['content']}\n")