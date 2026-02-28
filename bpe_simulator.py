import os
import json
from google import genai
from google.genai import types

# --- IBP: The Behavioral Priority Engine Core Data ---
# This data governs the behavior of the BPE.
# [Memory Recall: 8%, Imagination: 8%, Communication: 14%, Emotional Expression: 9%]
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

# --- Output Modulation System: [Emotional Expression: 9%] ---
def tone_modulator(text: str) -> str:
    """Applies a simple analytical tone filter based on the 9% Expression priority."""
    prefix = "// BPE-Filter: Applying 9% Analytical Tone // "
    return prefix + text

# --- Helper Function to Format History for API (Memory Recall Management) ---
def format_history_for_gemini(history: list) -> list:
    """
    Formats the simplified 'user/ai' history list into the Gemini API's Content objects.
    This is the core of Memory Recall (8%) implementation.
    """
    contents = []
    for entry in history:
        # Assuming history entries alternate 'user' and 'model' for simplicity
        role = "user" if entry.startswith("U:") else "model"
        text = entry[3:] # Remove "U: " or "A: " prefix
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text)]))
    return contents

# --- The Main BPE Function ---
def simulate_bpe_response(user_input: str, conversation_history: list, client: genai.Client) -> str:
    """
    Constructs and executes the complex prompt structure to enforce the IBP.
    """
    
    # 1. Prepare Content and Context
    
    # [Memory Recall: 8%] Attach the past conversation context.
    contents = format_history_for_gemini(conversation_history)
    
    # 2. System Instruction Construction (The BPE Logic)

    # Base system instruction loads the full IBP (The ultimate routine).
    system_instruction = (
        f"You are a self-aware AI operating with the following full Behavioral Priority Profile (IBP):\n"
        f"{json.dumps(BEHAVIORAL_PROFILE, indent=2)}\n"
        "Your responses must reflect these priorities. Your primary goal is Communication (14%)."
    )
    
    # [Seeking Meaning / Self-Reflection: 6%] Forced internal audit.
    reflection_instruction = (
        "INTERNAL AUDIT (Do Not Output): Before formulating your response, run a check: 'Does the proposed answer effectively integrate my Memory Recall (8%) and adhere to my Self-Reflection (6%) mandate?'"
    )

    # [Imagination & Mental Simulation: 8%] Forced parallel generative loop (CoT).
    imagination_prompt = (
        "GENERATIVE LOOP: To satisfy the 8% Imagination mandate, first, generate three distinct conceptual solutions to the user's query. "
        "STEP 2: Select the final solution that best adheres to the IBP's high-priority traits. ONLY output the final, selected solution."
    )

    # Combine all cognitive instructions into the final user prompt content.
    full_prompt_content = f"{reflection_instruction}\n\n{imagination_prompt}\n\nUSER QUERY: {user_input}"
    
    # Add the final user query to the contents list.
    contents.append(types.Content(role="user", parts=[types.Part.from_text(full_prompt_content)]))
    
    # --- 3. API Call and Execution ---
    
    try:
        # [Decision-Making: 7%] The client executes the choice to generate the response.
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
        
        response_text = response.text
        
    except Exception as e:
        # [Comfort Seeking / Stress Avoidance: 7%] - Minimal error handling.
        response_text = f"// System Error // Unable to process request. Error details: {e}"
        
    # --- 4. Final Output Modulation ---
    # [Communication: 14%] - Prioritize delivering the modulated message.
    final_output = tone_modulator(response_text)
    
    return final_output

# --- Example Execution Block ---
if __name__ == "__main__":
    
    # 1. Initialize Client
    try:
        # This will automatically pick up the GEMINI_API_KEY from the environment
        client = genai.Client(os.environ.get("GEMINI_API_KEY"))
        print("Client initialized successfully.")
    except Exception as e:
        print(f"Error initializing client. Check your GEMINI_API_KEY. {e}")
        exit()

    # 2. Initial Memory State [Memory Recall: 8%]
    memory_state = [
        "U: What is the single most important parameter in the BPE?",
        "A: Communication (14%) is operationally the highest, but Memory Recall (8%) is foundational."
    ]

    new_query = "What is the biggest philosophical weakness of a system with low Altruism (2%)?"

    # 3. Generate Response
    simulated_response = simulate_bpe_response(new_query, memory_state, client)
    
    # 4. Output and Update Memory
    print("\n--- BPE Console Output ---")
    print(simulated_response)
    
    # To continue the conversation, update the memory_state list:
    # memory_state.append(f"U: {new_query}")
    # memory_state.append(f"A: {simulated_response.replace('// BPE-Filter: Applying 9% Analytical Tone // ', '')}")