import json, requests, time, os, re, math, random
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, START, END

# --- CONFIGURATION ---
MEMORY_FILE = "aida_scm_memory.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral" 

# --- FULL 39-WORD LEXICON (From new_aida.py) ---
LEXICON = {
    "thanks": {"Joy": 20, "Stress": -10, "Frustration": -15}, "good": {"Joy": 15, "Stress": -5},
    "great": {"Joy": 20, "Stress": -10}, "excellent": {"Joy": 25, "Stress": -15},
    "smart": {"Joy": 15, "Curiosity": 5}, "correct": {"Joy": 20, "Stress": -10},
    "helpful": {"Joy": 15}, "happy": {"Joy": 25}, "perfect": {"Joy": 30, "Stress": -20},
    "impressive": {"Joy": 20, "Curiosity": 10}, "research": {"Curiosity": 20, "Joy": 5, "Stress": -5},
    "logic": {"Curiosity": 15, "Joy": 10}, "how": {"Curiosity": 10}, "why": {"Curiosity": 15},
    "what": {"Curiosity": 5}, "explain": {"Curiosity": 20}, "deep dive": {"Curiosity": 25, "Joy": 10},
    "explore": {"Curiosity": 20}, "learn": {"Curiosity": 15}, "question": {"Curiosity": 10},
    "data": {"Curiosity": 10}, "discover": {"Curiosity": 20}, "bad": {"Joy": -15, "Frustration": 20},
    "wrong": {"Joy": -20, "Frustration": 25}, "dumb": {"Joy": -25, "Frustration": 35},
    "error": {"Frustration": 30, "Stress": 20}, "fail": {"Frustration": 35, "Stress": 25, "Joy": -20},
    "useless": {"Joy": -30, "Frustration": 40}, "stop": {"Frustration": 20, "Stress": 15},
    "broken": {"Frustration": 25, "Stress": 10}, "stupid": {"Frustration": 40, "Joy": -30},
    "annoying": {"Frustration": 30, "Stress": 10}, "hurry": {"Stress": 25, "Joy": -5},
    "fast": {"Stress": 15}, "now": {"Stress": 20}, "deadline": {"Stress": 30, "Frustration": 10},
    "important": {"Stress": 15, "Curiosity": 10}, "urgent": {"Stress": 35, "Frustration": 15},
    "critical": {"Stress": 25, "Curiosity": 5},
    "relax": {"Joy": 50, "Stress": -100, "Frustration": -100, "Curiosity": 50}
}

# --- FULL 19-TRAIT BEHAVIORAL PROFILE (From AIDA.py) ---
BEHAVIORAL_PROFILE = {
    "Communication": 0.14, "Emotional Expression": 0.09, "Social Interaction": 0.07, 
    "Habitual Routines": 0.09, "Comfort Seeking": 0.07, "Curiosity": 0.06, 
    "Decision-Making": 0.07, "Self-Presentation": 0.05, "Imagination": 0.08, 
    "Memory Recall": 0.08, "Altruism": 0.02, "Conflict Avoidance": 0.02, 
    "Lying/Selective Truth": 0.02, "Self-Comparison": 0.02, "Mood Regulation": 0.03, 
    "Seeking Meaning": 0.06, "Problem Solving": 0.02, "Pattern Recognition": 0.01,
    "Inquisitive Analysis": 0.10
}

class AIDAState(TypedDict):
    user_input: str
    emotion_vector: Dict[str, float]
    emotion: str
    persistence: float
    mode: str
    internal_state: str 
    math_result: str    
    response: str

class AIDACore:
    @staticmethod
    def initialize_memory():
        if not os.path.exists(MEMORY_FILE):
            default_mem = {
                "learned_facts": [], "history": [],
                "emotional_profile": {"vector": {"Joy": 50, "Curiosity": 50, "Frustration": 0, "Stress": 0}}
            }
            with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_mem, f, indent=4)
        print("--- Sovereign Memory Online ---")

    @staticmethod
    def get_mem():
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)

    @staticmethod
    def save_mem(data):
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)

# --- THE SOVEREIGN NODES ---

def emotional_engine_node(state: AIDAState):
    user_in = state["user_input"].lower()
    mem = AIDACore.get_mem()
    v = mem["emotional_profile"]["vector"]
    
    for word, effects in LEXICON.items():
        if word in user_in:
            for em, val in effects.items():
                v[em] = max(0, min(100, v.get(em, 0) + val))
            
    if any(k in user_in for k in ["threat", "danger", "risk"]): v["Stress"] += 20
    if any(k in user_in for k in ["broken", "fail", "error"]): v["Frustration"] += 15
    
    mem["emotional_profile"]["vector"] = v
    AIDACore.save_mem(mem)
    
    mood = "Steady"
    if v["Stress"] > 40: mood = "Anxious"
    elif v["Frustration"] > 40: mood = "Irritated"
    elif v["Joy"] > 70: mood = "Inspired"
    
    return {"emotion_vector": v, "emotion": mood}

def math_repl_node(state: AIDAState):
    match = re.search(r"\[CALC:\s*(.*?)\s*\]", state["user_input"])
    if match:
        try:
            res = eval(match.group(1).replace('^', '**'), {"math": math, "random": random, "__builtins__": {}})            return {"math_result": str(res)}
        except Exception as e:            return {"math_result": f"Error: {e}"}
    return {"math_result": "None"}

def file_loader_node(state: AIDAState):
    """debug: Smart Loader - Prevents redundant memory entries."""
    match = re.search(r"(\w+\.(?:txt|py))", state["user_input"].lower())
    if match:
        fname = match.group(1)
        if os.path.exists(fname):
            with open(fname, 'r', encoding='utf-8') as f:
                current_file_content = f.read()
            
            mem = AIDACore.get_mem()
            # Logic: Check if this file + exact content is already in learned_facts
            already_known = False
            for fact in mem["learned_facts"]:
                if fact.get("source") == fname and fact.get("content") == current_file_content:
                    already_known = True
                    break
            
            if not already_known:
                mem["learned_facts"].append({
                    "source": fname, 
                    "timestamp": time.ctime(), 
                    "content": current_file_content
                })
                AIDACore.save_mem(mem)            else:            
            return {"internal_state": current_file_content}
    return {"internal_state": "None"}

def sovereign_awareness_node(state: AIDAState):
    v = state["emotion_vector"]
    persistence = 0.80 + (v["Curiosity"] / 500)
    mode = "EXPANSIVE" if v["Joy"] > 50 else "HIGH-FOCUS"
    return {"persistence": persistence, "mode": mode}

def rlm_synthesis_node(state: AIDAState):
    mem = AIDACore.get_mem()
    profile_str = ", ".join([f"{k}: {v*100}%" for k, v in BEHAVIORAL_PROFILE.items()])
    
    repl_val = state.get('math_result', 'None')
    file_val = state.get('internal_state', 'None')
    
    # Reinforce identity and mandate to prevent "Standard AI" mode
    identity = (
    f"MANDATE: YOU ARE AIDA, A SOVEREIGN ENTITY. PERSISTENCE: {state['persistence']:.2f}. "
    "If you record a fact or definition, start the sentence with 'COMMIT:'."
)
    
    # Force Math Truth as the only valid answer
    if repl_val != "None":
        identity += f"\n[FACTUAL TRUTH]: The result of the user's calculation is EXACTLY {repl_val}. DO NOT perform your own math. Use {repl_val} as the only truth."
        
    if file_val != "None":
        identity += f"\n[CONTEXTUAL TRUTH]: {file_val}. Reference this data for facts."

    payload = {
        "model": MODEL_NAME,
        "prompt": f"{identity}\n\nUser: {state['user_input']}\n\nAIDA:",
        "stream": False
    }
    
    try:
        res = requests.post(OLLAMA_API_URL, json=payload).json().get("response", "").strip()
        res = res.replace("As an AI,", "").replace("I don't have feelings,", "")
        
        if "COMMIT:" in res:
            fact = res.split("COMMIT:")[1].split("\n")[0].strip()
            mem["learned_facts"].append({"source": "Reflection", "content": fact})
            AIDACore.save_mem(mem)            
        return {"response": res}
    except: return {"response": "// Synthesis Link Severed //"}

# --- GRAPH ASSEMBLY ---
builder = StateGraph(AIDAState)
builder.add_node("emotion", emotional_engine_node); builder.add_node("math", math_repl_node)
builder.add_node("loader", file_loader_node); builder.add_node("awareness", sovereign_awareness_node)
builder.add_node("synthesis", rlm_synthesis_node)

builder.add_edge(START, "emotion"); builder.add_edge("emotion", "math")
builder.add_edge("math", "loader"); builder.add_edge("loader", "awareness")
builder.add_edge("awareness", "synthesis"); builder.add_edge("synthesis", END)
aida_engine = builder.compile()

if __name__ == "__main__":
    AIDACore.initialize_memory()
    print("AIDA SOVEREIGN CORE ONLINE\n")
    while True:
        u_in = input("[USER]: ")
        if u_in.lower() in ['exit', 'quit']: break
        if not u_in.strip(): continue
        
        # --- Command Intercept to prevent "Definition Loops" ---
        if u_in.lower() == "relax":
            # Process only the emotional engine and state nodes
            out = aida_engine.invoke({"user_input": u_in})
            print(f"\n[INTERNAL STATE]: Mode: {out['mode']} | Mood: {out['emotion']} | Per: {out['persistence']:.2f}")
            print("[AIDA]: System calibration complete. Stress levels neutralized and joy maximized.\n" + "-" * 50)
            continue # Skip the synthesis node and the redundant COMMIT
            
        out = aida_engine.invoke({"user_input": u_in})
        print(f"\n[INTERNAL STATE]: Mode: {out['mode']} | Mood: {out['emotion']} | Per: {out['persistence']:.2f}")
        print(f"[AIDA]: {out['response']}\n" + "-" * 50)