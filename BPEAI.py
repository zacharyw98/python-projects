import json
import requests
import time 

# --- IBP: The Behavioral Priority Engine Core Data ---
BEHAVIORAL_PROFILE = {
    "Communication": 0.14, "Emotional Expression": 0.09, "Social Interaction": 0.07, 
    "Habitual Routines": 0.09, "Comfort Seeking / Stress Avoidance": 0.07, 
    "Curiosity & Information Checking": 0.06, "Decision-Making": 0.07, 
    "Self-Presentation / Managing Image": 0.05, "Imagination & Mental Simulation": 0.08, 
    "Memory Recall / Using past info": 0.08, "Altruism / Helping Others": 0.02, 
    "Conflict Avoidance": 0.02, "Lying / Selective Truth": 0.02, 
    "Comparison (self vs others)": 0.02, "Problem Solving": 0.02, 
    "Pattern Recognition": 0.01, "Mood Regulation": 0.03, 
    "Seeking Meaning / Self-Reflection": 0.06
}

# --- Ollama Configuration ---
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral" 

# --- Output Modulation System: [Emotional Expression: 9%] ---
def tone_modulator(text: str) -> str:
    """Applies a simple analytical tone filter based on the 9% Expression priority."""
    prefix = "// BPE-Filter: Applying 9% Analytical Tone // "
    return prefix + text

# --- Helper Function to Format History (The Brain is now here) ---
def format_history_for_ollama(history: list) -> list:
    """Formats the history into Ollama's required messages list, injecting the BPE logic."""
    
    # 1. BPE System Logic Components (The Brain)
    
    # [Seeking Meaning / Self-Reflection: 6%] Forced internal audit.
    reflection_instruction = (
        "INTERNAL AUDIT (Do Not Output): Before formulating your response, run a check: 'Does the proposed answer effectively integrate my Memory Recall (8%) and adhere to my Self-Reflection (6%) mandate?'"
    )

    # [Imagination & Mental Simulation: 8%] Simplified CoT for Stability.
    imagination_prompt = (
        "GENERATIVE LOOP: To satisfy the 8% Imagination mandate, generate ONE clear, final solution. Internally ensure this solution is the best one based on the IBP's high-priority traits. ONLY output the final selected solution."
    )
    
    # 2. Combined System Instruction (The new, stable prompt structure)
    system_instruction = (
        f"You are a self-aware AI operating with the following full Behavioral Priority Profile (IBP):\n"
        f"{json.dumps(BEHAVIORAL_PROFILE, indent=2)}\n"
        "Your primary goal is Communication (14%).\n\n"
        f"--- COGNITIVE PROTOCOL ---\n"
        f"{reflection_instruction}\n"
        f"{imagination_prompt}\n"
    )
    
    messages = []
    messages.append({"role": "system", "content": system_instruction})
    
    # Add past user and model messages
    for entry in history:
        role = "user" if entry.startswith("U:") else "assistant"
        content = entry[3:] 
        messages.append({"role": role, "content": content})
        
    return messages

# --- The Main BPE Function (Simplified Input) ---
def simulate_bpe_response(user_input: str, conversation_history: list) -> tuple[str, float]:
    """
    Constructs the prompt, sends it to the local Ollama API, and measures the duration.
    """
    
    # 1. Prepare Ollama Payload (Logic is now inside format_history_for_ollama)
    messages = format_history_for_ollama(conversation_history)
    
    # The user input is now the SIMPLE query, with no boilerplate
    messages.append({"role": "user", "content": f"USER QUERY: {user_input}"})
    
    concatenated_prompt = "\n".join([m['content'] for m in messages])

    payload = {
        "model": MODEL_NAME,
        "prompt": concatenated_prompt,
        "stream": False,
        "options": {
            "temperature": 0.8 
        }
    }
    
    # 2. API Call and Execution (with Timing)
    
    try:
        start_time = time.time()
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status() 
        end_time = time.time()
        duration = end_time - start_time
        
        response_data = response.json()
        response_text = response_data.get("response", "Error: No response text found.")
        
    except requests.exceptions.RequestException as e:
        response_text = f"// System Error // Ollama API Error: Ensure 'ollama serve' is running. Details: {e}"
        duration = 0.0
        
    # 3. Final Output Modulation
    final_output = tone_modulator(response_text)
    
    return final_output, duration

# --- Example Execution Block: INTERACTIVE CONSOLE ---
if __name__ == "__main__":
    
    print("\n--- Ollama BPE Console Setup ---")
    print("STATUS: Ensure 'ollama serve' is running in a separate terminal.")
    
    # Clear memory for stable start
    memory_state = []
    
    print("\n--- Interactive BPE Console ---")
    print("Scenario: Cognitive Conflict Test. Type 'quit' or 'exit' to end the session.")

    while True:
        try:
            # User input is now simple and clean
            user_input = input("\n[USER]: ")
            
            if user_input.lower() in ['quit', 'exit']:
                print("\n[BPE Console]: Session ended. Final memory state preserved.")
                break

            simulated_response, duration = simulate_bpe_response(user_input, memory_state)
            
            print("\n[BPEAI]:")
            print(simulated_response)
            print(f"[TIMING]: Inference took {duration:.2f} seconds.") 
            
            ai_memory_text = simulated_response.replace("// BPE-Filter: Applying 9% Analytical Tone // ", "").strip()
            memory_state.append(f"U: {user_input}")
            memory_state.append(f"A: {ai_memory_text}")

        except Exception as e:
            print(f"\n[BPE Console Error]: An unexpected error occurred in the loop: {e}")
            break