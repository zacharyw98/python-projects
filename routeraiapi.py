## openrouter_api_test.py

import requests
import json
import os # Import the os module for path manipulation

# This script helps you test your OpenRouter API key and see available models.

CONFIG_FILE = "config.json" # Define the name of the configuration file
FREE_MODELS_FILE = "free_models.json" # Define the name of the file for free models
NOT_FREE_MODELS_FILE = "not_free_models.json" # Define the name of the file for non-free models

def load_api_key():
    """
    Loads the API key from a config.json file. If the file doesn't exist
    or the key is not found, it prompts the user to enter it and saves it.

    Returns:
        str: The OpenRouter API key.
    """
    api_key = None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                api_key = config.get("openrouter_api_key")
                if api_key:
                    print(f"API key loaded from {CONFIG_FILE}.")
                else:
                    print(f"'{CONFIG_FILE}' found, but 'openrouter_api_key' not in it.")
        except json.JSONDecodeError:
            print(f"Error reading {CONFIG_FILE}. It might be corrupted. Please delete it and try again.")
        except Exception as e:
            print(f"An unexpected error occurred while loading {CONFIG_FILE}: {e}")

    if not api_key:
        print("\nOpenRouter API key not found or could not be loaded.")
        api_key = input("Please enter your OpenRouter API key: ").strip()
        if api_key:
            save_api_key(api_key)
        else:
            print("No API key entered. Exiting.")
            exit() # Exit if no API key is provided

    return api_key

def save_api_key(api_key: str):
    """
    Saves the API key to a config.json file.

    Args:
        api_key (str): The OpenRouter API key to save.
    """
    config = {"openrouter_api_key": api_key}
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"API key saved to {CONFIG_FILE}.")    except Exception as e:
        print(f"Error saving API key to {CONFIG_FILE}: {e}")

def save_models_to_file(models_list: list, filename: str, description: str):
    """
    Saves a list of models to a specified JSON file.

    Args:
        models_list (list): A list of dictionaries, where each dictionary
                            represents a model.
        filename (str): The name of the file to save the models to.
        description (str): A description of the models being saved (e.g., "free models").
    """
    try:
        with open(filename, 'w') as f:
            json.dump(models_list, f, indent=4)
        print(f"\nSuccessfully saved {len(models_list)} {description} to {filename}.")    except Exception as e:
        print(f"Error saving {description} to {filename}: {e}")


def test_openrouter_api(api_key: str):
    """
    Tests the OpenRouter API by fetching a list of available models.
    Filters out models ending with "(free)" and saves them to a separate file,
    and saves the rest to another file.

    Args:
        api_key (str): Your OpenRouter API key.
    """
    # OpenRouter API endpoint to list models
    url = "https://openrouter.ai/api/v1/models"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # Make the GET request to the OpenRouter API
        response = requests.get(url, headers=headers)
        # Check if the request was successful (HTTP status 200)
        if response.status_code == 200:
            # Parse the JSON response
            models_data = response.json()
            free_models_list = []
            not_free_models_list = [] # New list for non-free models

            print("\nSuccessfully connected to OpenRouter API!")
            print("Available Models:")

            # Iterate through the models and print their IDs and names
            if 'data' in models_data and isinstance(models_data['data'], list):
                for model in models_data['data']:
                    model_id = model.get('id', 'N/A')
                    model_name = model.get('name', 'N/A')
                    print(f"- ID: {model_id}, Name: {model_name}")

                    # Check if the model name ends with "(free)"
                    if model_name.lower().endswith("(free)"):
                        free_models_list.append(model)
                    else:
                        not_free_models_list.append(model) # Add to not-free list
            else:
                print("No model data found in the response or unexpected format.")
            # Save the identified free models to a separate file
            if free_models_list:
                save_models_to_file(free_models_list, FREE_MODELS_FILE, "free models")
            else:
                print(f"\nNo models ending with '(free)' were found to save to {FREE_MODELS_FILE}.")

            # Save the identified not-free models to a separate file
            if not_free_models_list:
                save_models_to_file(not_free_models_list, NOT_FREE_MODELS_FILE, "not-free models")
            else:
                print(f"\nNo models not ending with '(free)' were found to save to {NOT_FREE_MODELS_FILE}.")

        elif response.status_code == 401:
            print("\nError: Unauthorized. Your API key might be invalid or missing.")
            print("Please double-check your OpenRouter API key.")
        else:
            print(f"\nError: Failed to fetch models. Status code: {response.status_code}")
            try:
                error_details = response.json()            except json.JSONDecodeError:
    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred during the API request: {e}")
    except json.JSONDecodeError:
        print("\nError: Could not decode JSON response from the API.")
        print(f"Raw response content: {response.text}")

if __name__ == "__main__":
    # Load or prompt for the API key
    openrouter_api_key = load_api_key()

    # Only proceed if an API key was successfully obtained
    if openrouter_api_key:
        test_openrouter_api(openrouter_api_key)

