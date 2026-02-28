import requests
from bs4 import BeautifulSoup
import re
import json
import time
import os
import asyncio
import aiohttp
import signal
import sys

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    print("Warning: tqdm library not found. Falling back to simple text progress.")
    TQDM_AVAILABLE = False

# --- Global variables to be accessed by signal handler ---
_existing_matched_items = []
_existing_unmatched_items = []
_existing_error_items = []
_newly_found_matched_items = []
_newly_found_unmatched_items = []
_newly_found_error_items = []
_matched_output_filename = ""
_unmatched_output_filename = ""
_error_output_filename = ""
_tqdm_pbar = None

# --- Helper functions ---
def load_existing_data(filename):
    """
    Loads data from a JSON file. Returns an empty list if the file doesn't exist or is empty.
    """
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {filename}. Starting with empty data.")
            return []
    return []

def save_data_to_json(data, filename):
    """
    Saves a list of dictionaries to a JSON file.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved data to '{filename}'")
    except IOError as e:
        print(f"Error saving to JSON file '{filename}': {e}")

async def get_wowhead_item_info_async(session, url):
    """
    Asynchronously fetches the item name and ID from a given Wowhead item URL.
    Prioritizes extracting the name from the URL slug. If not found in URL,
    it falls back to fetching the page.

    Args:
        session (aiohttp.ClientSession): The aiohttp client session.
        url (str): The full URL of the Wowhead item page.

    Returns:
        tuple: (dict, int/str) - (item_info_dict, HTTP_status_code) on success,
                               - (None, 404) if not found,
                               - (None, 'network_error') for connection issues,
                               - (None, 'parsing_error') for HTML parsing issues,
                               - (None, 'extraction_failed') if page fetched but info missing,
                               - (None, 'no_id_in_url') if URL itself is malformed.
    """
    item_name = None
    item_id = None

    match = re.search(r'/item=(\d+)(?:/([^/]+))?', url)
    if match:
        item_id = match.group(1)
        if match.group(2):
            item_name = ' '.join([word.capitalize() for word in match.group(2).replace('-', ' ').split(' ')])

    if item_name and item_id:
        return {'name': item_name, 'id': item_id}, 200
    elif item_id:
        try:
            async with session.get(url) as response:
                if response.status == 404:
                    return None, 404
                response.raise_for_status()

                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')

                h1_tag = soup.find('h1')
                if h1_tag:
                    item_name = h1_tag.get_text(strip=True)
                else:
                    og_title_tag = soup.find('meta', property='og:title')
                    if og_title_tag and og_title_tag.get('content'):
                        item_name = og_title_tag['content'].split(' - Item - WoWHead')[0].strip()

                if item_name and item_id:
                    return {'name': item_name, 'id': item_id}, 200
                else:
                    return None, 'extraction_failed'

        except aiohttp.ClientResponseError as e:
            return None, e.status
        except aiohttp.ClientError as e:
            return None, 'network_error'
        except Exception as e:
            print(f"An unexpected error occurred for {url}: {e}")
            return None, 'parsing_error'
    else:
        return None, 'no_id_in_url'

# --- Function to load settings ---
def load_settings(settings_filename="settings.json"):
    """
    Loads settings from a JSON file. If the file doesn't exist or is invalid,
    it creates a default settings file.
    """
    default_settings = {
        "initial_start_id": 1,
        "scan_block_size": 5000,
        "request_delay": 0.01,
        "scan_timeout_minutes": 5,
        "enable_timeout": True,
        "concurrent_requests_limit": 50,
        "consecutive_not_found_threshold": 500,
        "target_item_names": [
            "mining",
            "herbalism",
            "pick",
            "ore",
            "herb",
            "flower",
            "plant",
            "root",
            "leaf",
            "bloom",
            "flytrap",
            "weed",
            "bud",
            "khorium",
            "bar"
        ],
        "matched_output_filename": "wowhead_matched_items.json",
        "unmatched_output_filename": "wowhead_unmatched_items.json",
        "error_output_filename": "wowhead_error_ids.json"
    }

    if os.path.exists(settings_filename) and os.path.getsize(settings_filename) > 0:
        try:
            with open(settings_filename, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                for key, default_value in default_settings.items():
                    if key not in settings:
                        settings[key] = default_value
                return settings
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from {settings_filename}. Creating a new default settings file.")
            save_data_to_json(default_settings, settings_filename)
            return default_settings
    else:
        print(f"'{settings_filename}' not found or is empty. Creating a new default settings file.")
        save_data_to_json(default_settings, settings_filename)
        return default_settings

# --- Signal Handler ---
def signal_handler(sig, frame):
    """
    Handles termination signals (e.g., Ctrl+C) to save current progress.
    """
    print(f"\nCaught signal {sig}. Saving current progress before exiting...")

    global _tqdm_pbar
    if _tqdm_pbar is not None:
        _tqdm_pbar.close()

    final_matched_items = _existing_matched_items + _newly_found_matched_items
    final_unmatched_items = _existing_unmatched_items + _newly_found_unmatched_items
    final_error_items = _existing_error_items + _newly_found_error_items

    seen_matched_ids_temp = set()
    unique_final_matched_items = []
    for item in final_matched_items:
        if item['id'] not in seen_matched_ids_temp:
            unique_final_matched_items.append(item)
            seen_matched_ids_temp.add(item['id'])

    seen_unmatched_ids_temp = set()
    unique_final_unmatched_items = []
    for item in final_unmatched_items:
        if item['id'] not in seen_unmatched_ids_temp:
            unique_final_unmatched_items.append(item)
            seen_unmatched_ids_temp.add(item['id'])

    seen_error_ids_temp = set()
    unique_final_error_items = []
    for item in final_error_items:
        if item['id'] not in seen_error_ids_temp:
            unique_final_error_items.append(item)
            seen_error_ids_temp.add(item['id'])

    save_data_to_json(unique_final_matched_items, _matched_output_filename)
    save_data_to_json(unique_final_unmatched_items, _unmatched_output_filename)
    save_data_to_json(unique_final_error_items, _error_output_filename)

    print("Progress saved. Exiting.")
    sys.exit(0)

# --- Main asynchronous scanning logic ---
async def main():
    global _existing_matched_items, _existing_unmatched_items, _existing_error_items, \
           _newly_found_matched_items, _newly_found_unmatched_items, _newly_found_error_items, \
           _matched_output_filename, _unmatched_output_filename, _error_output_filename, _tqdm_pbar

    settings = load_settings()

    # --- Configuration from settings ---
    initial_start_id = settings["initial_start_id"]
    scan_block_size = settings["scan_block_size"]
    request_delay = settings["request_delay"]
    scan_timeout_minutes = settings["scan_timeout_minutes"]
    enable_timeout = settings["enable_timeout"]
    concurrent_requests_limit = settings["concurrent_requests_limit"]
    consecutive_not_found_threshold = settings["consecutive_not_found_threshold"]
    target_item_names = settings["target_item_names"]
    _matched_output_filename = settings["matched_output_filename"]
    _unmatched_output_filename = settings["unmatched_output_filename"]
    _error_output_filename = settings["error_output_filename"]

    exact_match_keywords = ["ore", "bar"]
    substring_match_keywords = [kw for kw in target_item_names if kw.lower() not in [e.lower() for e in exact_match_keywords]]

    print("--- Starting Wowhead Item Scraper (Concurrent Incremental Scan Mode) ---")
    print(f"Scanning in blocks of {scan_block_size} IDs. Concurrency limit: {concurrent_requests_limit} requests.")
    if enable_timeout:
        print(f"Each scan block will stop after {scan_timeout_minutes} minutes if not completed.")
    else:
        print("Scan timeout is DISABLED for each block.")

    if target_item_names:
        print(f"Filtering for items containing keywords: {', '.join(target_item_names)}")
        if exact_match_keywords:
            print(f"  (Note: '{', '.join(exact_match_keywords)}' will be matched as whole words only)")
    else:
        print("No target keywords specified. All found items will be saved to matched file.")

    _existing_matched_items = load_existing_data(_matched_output_filename)
    _existing_unmatched_items = load_existing_data(_unmatched_output_filename)
    _existing_error_items = load_existing_data(_error_output_filename)

    scanned_ids_set = set(item['id'] for item in _existing_matched_items + _existing_unmatched_items + _existing_error_items)
    print(f"Loaded {len(scanned_ids_set)} previously scanned unique item IDs (including errors).")

    if scanned_ids_set:
        max_scanned_id = max(int(id_str) for id_str in scanned_ids_set)
        current_scan_start_id = max_scanned_id + 1
        print(f"Resuming scan from ID: {current_scan_start_id}")
    else:
        current_scan_start_id = initial_start_id
        print(f"Starting new scan from ID: {current_scan_start_id}")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # --- Main scanning loop for blocks ---
    while True:
        block_start_id = current_scan_start_id
        block_end_id = current_scan_start_id + scan_block_size - 1

        print(f"\n--- Scanning Block: IDs {block_start_id} to {block_end_id} ---")

        _newly_found_matched_items = []
        _newly_found_unmatched_items = []
        _newly_found_error_items = []
        start_time = time.time()
        consecutive_not_found_count = 0

        async with aiohttp.ClientSession() as session:
            semaphore = asyncio.Semaphore(concurrent_requests_limit)

            async def fetch_and_process_item(item_id):
                async with semaphore:
                    url = f"https://www.wowhead.com/item={item_id}"
                    info, status_or_error_type = await get_wowhead_item_info_async(session, url)
                    return item_id, info, status_or_error_type # Return all three pieces of info

            tasks_to_run = []
            for item_id_to_scan in range(block_start_id, block_end_id + 1):
                if str(item_id_to_scan) not in scanned_ids_set:
                    task = asyncio.create_task(fetch_and_process_item(item_id_to_scan))
                    tasks_to_run.append(task)

            if not tasks_to_run:
                print(f"All IDs in block {block_start_id}-{block_end_id} already scanned or no new IDs to process.")
                current_scan_start_id = block_end_id + 1
                continue

            if TQDM_AVAILABLE:
                _tqdm_pbar = tqdm(asyncio.as_completed(tasks_to_run), total=len(tasks_to_run), desc=f"Fetching IDs {block_start_id}-{block_end_id}", unit="ID")
                pbar_iterable = _tqdm_pbar
            else:
                pbar_iterable = asyncio.as_completed(tasks_to_run)

            block_terminated_by_not_found = False

            for future in pbar_iterable:
                if enable_timeout:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > scan_timeout_minutes * 60:
                        print(f"\nScan block stopped: Exceeded {scan_timeout_minutes} minute timeout.")
                        if TQDM_AVAILABLE:
                            _tqdm_pbar.close()
                        for remaining_task in tasks_to_run:
                            if not remaining_task.done():
                                remaining_task.cancel()
                        break

                item_id_from_future = None # Initialize to None
                info = None
                status_or_error_type = None

                try:
                    item_id_from_future, info, status_or_error_type = await future # Unpack all three
                except asyncio.CancelledError:
                    continue
                except Exception as e:
                    # This catches unexpected exceptions during task execution that weren't caught by get_wowhead_item_info_async
                    # The original item_id should be available if `fetch_and_process_item` was called.
                    # This is a fallback for truly unhandled errors.
                    print(f"Unhandled exception during task completion (ID might be unknown): {e}")
                    # If we can't get the ID reliably here, it's safer to just log the general issue.
                    # For now, we'll use a placeholder if item_id_from_future is not set.
                    item_id_from_future = item_id_from_future or 'unknown_id_from_unhandled_exception'
                    info = None
                    status_or_error_type = 'unhandled_task_exception'

                if info: # Successfully got item info
                    scanned_ids_set.add(info['id'])
                    item_name_lower = info['name'].lower()
                    is_matched = False

                    for keyword in exact_match_keywords:
                        if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', item_name_lower):
                            is_matched = True
                            break
                    
                    if not is_matched:
                        for keyword in substring_match_keywords:
                            if keyword.lower() in item_name_lower:
                                is_matched = True
                                break

                    if is_matched:
                        _newly_found_matched_items.append(info)
                        if TQDM_AVAILABLE:
                            _tqdm_pbar.set_postfix_str(f"Found: {info['name']}")
                    else:
                        _newly_found_unmatched_items.append(info)
                        if TQDM_AVAILABLE:
                            _tqdm_pbar.set_postfix_str(f"Unmatched: {info['name']}")
                    consecutive_not_found_count = 0 # Reset counter on success
                else: # Item info was None (error or not found)
                    id_for_error = str(item_id_from_future) # Use the ID directly from the future result

                    if status_or_error_type == 404:
                        consecutive_not_found_count += 1
                        if TQDM_AVAILABLE:
                            _tqdm_pbar.set_postfix_str(f"Not found (Consecutive: {consecutive_not_found_count})")
                    else: # It's an error other than 404
                        _newly_found_error_items.append({'id': id_for_error, 'error_type': status_or_error_type})
                        scanned_ids_set.add(id_for_error) # Mark as scanned so we skip it next time
                        consecutive_not_found_count = 0 # Reset consecutive counter on a non-404 error
                        if TQDM_AVAILABLE:
                            _tqdm_pbar.set_postfix_str(f"Error: {status_or_error_type} (ID: {id_for_error})")

                if consecutive_not_found_count >= consecutive_not_found_threshold:
                    print(f"\nReached {consecutive_not_found_threshold} consecutive non-found IDs. Assuming end of active IDs.")
                    block_terminated_by_not_found = True
                    if TQDM_AVAILABLE:
                        _tqdm_pbar.close()
                    for remaining_task in tasks_to_run:
                        if not remaining_task.done():
                            remaining_task.cancel()
                    break

                await asyncio.sleep(request_delay)

        # --- Save results after each block ---
        _existing_matched_items.extend(_newly_found_matched_items)
        _existing_unmatched_items.extend(_newly_found_unmatched_items)
        _existing_error_items.extend(_newly_found_error_items)

        seen_matched_ids_temp = set()
        unique_final_matched_items = []
        for item in _existing_matched_items:
            if item['id'] not in seen_matched_ids_temp:
                unique_final_matched_items.append(item)
                seen_matched_ids_temp.add(item['id'])

        seen_unmatched_ids_temp = set()
        unique_final_unmatched_items = []
        for item in _existing_unmatched_items:
            if item['id'] not in seen_unmatched_ids_temp:
                unique_final_unmatched_items.append(item)
                seen_unmatched_ids_temp.add(item['id'])

        seen_error_ids_temp = set()
        unique_final_error_items = []
        for item in _existing_error_items:
            if item['id'] not in seen_error_ids_temp:
                unique_final_error_items.append(item)
                seen_error_ids_temp.add(item['id'])

        _existing_matched_items[:] = unique_final_matched_items
        _existing_unmatched_items[:] = unique_final_unmatched_items
        _existing_error_items[:] = unique_final_error_items

        save_data_to_json(_existing_matched_items, _matched_output_filename)
        save_data_to_json(_existing_unmatched_items, _unmatched_output_filename)
        save_data_to_json(_existing_error_items, _error_output_filename)

        print(f"\nBlock {block_start_id}-{block_end_id} completed.")
        print(f"Total matched items found so far: {len(_existing_matched_items)}")
        print(f"Total unmatched items found so far: {len(_existing_unmatched_items)}")
        print(f"Total error items found so far: {len(_existing_error_items)}")

        if block_terminated_by_not_found:
            while True:
                user_input = input("It appears all existing IDs have been scanned. Do you want to start a NEW scan from ID 1 (re-check all, skipping existing), or QUIT? (new/quit): ").lower().strip()
                if user_input in ['new', 'n']:
                    print("Starting a new scan from ID 1. Previously found items will be skipped.")
                    current_scan_start_id = initial_start_id
                    break
                elif user_input in ['quit', 'q']:
                    print("Stopping scan as requested.")
                    signal_handler(None, None)
                    return
                else:
                    print("Invalid input. Please type 'new' or 'quit'.")
        else:
            while True:
                user_input = input("Scan block finished. Do you want to continue to the next block? (yes/no): ").lower().strip()
                if user_input in ['yes', 'y']:
                    current_scan_start_id = block_end_id + 1
                    break
                elif user_input in ['no', 'n']:
                    print("Stopping scan as requested.")
                    signal_handler(None, None)
                    return
                else:
                    print("Invalid input. Please type 'yes' or 'no'.")

if __name__ == "__main__":
    asyncio.run(main())
