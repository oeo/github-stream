import os
import re
import time
import github3
import base64
import requests
import argparse
from datetime import datetime
from scanner.analyzer import Analyzer
from scanner.llm_analyzer import LLMAnalyzer
from scanner.config import (
    TARGET_EXTENSIONS, GITHUB_TOKEN, POLL_INTERVAL, MAX_FILE_SIZE,
    SCAN_MODE, LLM_PROVIDER, MODEL_CONFIGS, LLM_MODEL_KEY, OLLAMA_CONFIG,
    MAX_FILES_PER_REPO
)
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import signal

def signal_handler(sig, frame):
    print(f"Caught signal {sig}")

    # @todo: perform cleanup here

    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler) # Also handle Ctrl+C

# --- Global variable to control skipping ---
skip_repo = threading.Event()

# --- Queues for multi-stage processing ---
llm_analysis_queue = Queue()

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Configure logging
import logging
logging.basicConfig(
    filename='scanner/logs/detections.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logging.getLogger("github3").setLevel(logging.WARNING)


# --- Directory for saving detected files ---
LEAKS_DIR = "detected_leaks"
if not os.path.exists(LEAKS_DIR):
    os.makedirs(LEAKS_DIR)

def log_detection(key_type, file_path, line_number, match, raw_url, file_size):
    """Logs a detected key to the console and a file."""
    # Format file size for readability
    if file_size < 1024:
        size_str = f"{file_size} B"
    else:
        size_str = f"{file_size / 1024:.2f} KB"
        
    log_message = (
        f"Detected {key_type} in {file_path} (Size: {size_str}) at line {line_number}: {match}\n"
        f"  -> Raw file URL: {raw_url}"
    )
    print(f"{Colors.FAIL}{Colors.BOLD}[!] REAL KEY DETECTED:\n{log_message}{Colors.ENDC}")
    logging.info(log_message)

def save_leaked_file(file_path, content, detections, raw_url, file_size):
    """Saves the content of a file that contains a detected key, with a metadata header."""
    try:
        # Sanitize the filename to be safe for local storage
        safe_filename = file_path.replace('/', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        leak_file_path = os.path.join(LEAKS_DIR, f"{timestamp}_{safe_filename}")
        
        if file_size < 1024:
            size_str = f"{file_size} B"
        else:
            size_str = f"{file_size / 1024:.2f} KB"
        
        header = "# --- DETECTION METADATA ---\n"
        header += f"# File Path: {file_path}\n"
        header += f"# File Size: {size_str}\n"
        header += f"# Raw URL: {raw_url}\n"
        header += "#\n"
        header += "# Detections:\n"
        for detection in detections:
            # Truncate long lines for readability in the header
            line_preview = (detection['line'][:75] + '...') if len(detection['line']) > 75 else detection['line']
            header += f"# - Line {detection['line_num']}: {detection['classification']} -> \"{line_preview}\"\n"
        header += "# --- END METADATA ---\n\n"
        
        full_content_with_header = header + content
        
        with open(leak_file_path, 'w', encoding='utf-8') as f:
            f.write(full_content_with_header)
        
        print(f"  -> {Colors.FAIL}Saved leaked file with metadata to: {leak_file_path}{Colors.ENDC}")
    except Exception as e:
        print(f"  -> {Colors.FAIL}Error saving leaked file {file_path}: {e}{Colors.ENDC}")

def user_input_thread():
    """A thread to listen for the 's' key to skip the current repository."""
    while True:
        if sys.stdin.isatty():
            user_input = input()
            if user_input.strip().lower() == 's':
                print(f"{Colors.WARNING}Skip command received. Finishing current file and skipping rest of repo...{Colors.ENDC}")
                skip_repo.set()

def download_file_content(url):
    """Downloads the content of a file from its GitHub API URL."""
    try:
        resp = requests.get(url, headers={'Authorization': f'token {GITHUB_TOKEN}'})
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"  -> {Colors.FAIL}Error downloading content: {e}{Colors.ENDC}")
        return None

def llm_worker(llm_analyzer, verbose=False):
    """A worker thread that consumes files from a queue and performs LLM analysis."""
    while True:
        file_to_process = llm_analysis_queue.get()
        if file_to_process is None:  # Sentinel value to stop the thread
            break

        # Unpack the data for the file
        file_path = file_to_process['file_path']
        decoded_content = file_to_process['decoded_content']
        raw_url = file_to_process['raw_url']
        file_size = file_to_process['file_size']
        potential_leaks = file_to_process['potential_leaks']

        real_key_detections = []
        
        # Parallel LLM analysis for all snippets in this file
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_leak = {
                executor.submit(llm_analyzer.classify_snippet, leak['snippet']): leak
                for leak in potential_leaks
            }
            for future in as_completed(future_to_leak):
                leak_info = future_to_leak[future]
                classification = future.result()
                if "REAL_KEY" in classification:
                    if verbose:
                        print(f"  -> {Colors.OKBLUE}LLM classification for {file_path}: {classification}{Colors.ENDC}")
                    
                    detection = {
                        "classification": classification,
                        "line_num": leak_info['line_num'],
                        "line": leak_info['line']
                    }
                    real_key_detections.append(detection)
                    log_detection(classification, file_path, leak_info['line_num'], leak_info['line'].strip(), raw_url, file_size)

        if real_key_detections:
            save_leaked_file(file_path, decoded_content, real_key_detections, raw_url, file_size)
        
        llm_analysis_queue.task_done()

def print_startup_info(args):
    """Prints a summary of the current configuration."""
    print(f"{Colors.HEADER}--- github-stream ---{Colors.ENDC}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Mode: {'Verbose' if args.verbose else 'Standard'}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] LLM Provider: {LLM_PROVIDER}")
    if LLM_PROVIDER == 'ollama':
        print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Ollama Model: {OLLAMA_CONFIG['model']}")
    else:
        print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] HuggingFace Model: {MODEL_CONFIGS[LLM_MODEL_KEY]['name']}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Worker Threads (CPUs): {args.cpus}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Max Files per Repo: {MAX_FILES_PER_REPO}")
    print(f"{Colors.HEADER}---------------------------{Colors.ENDC}")


def monitor_github_events(args):
    """Monitors GitHub for new PushEvents and scans the associated file contents."""
    verbose = args.verbose
    if GITHUB_TOKEN == "YOUR_NEW_GITHUB_TOKEN_HERE" or not GITHUB_TOKEN:
        print("Please add your GitHub token to scanner/config.py")
        return

    # Initialize the analyzers
    analyzer = Analyzer()
    llm_analyzer = LLMAnalyzer(verbose=verbose)

    # Start the LLM worker threads
    num_llm_workers = args.cpus
    llm_workers = []
    for _ in range(num_llm_workers):
        worker = threading.Thread(target=llm_worker, args=(llm_analyzer, verbose), daemon=True)
        worker.start()
        llm_workers.append(worker)

    gh = github3.login(token=GITHUB_TOKEN)
    last_event_id = None

    if verbose:
        print("Monitoring GitHub for new commits... (Press 's' then Enter to skip a repository)")
    else:
        print("Monitoring GitHub for new commits...")

    # Start the user input thread
    input_thread = threading.Thread(target=user_input_thread, daemon=True)
    input_thread.start()

    while True:
        try:
            if verbose:
                print(f"{Colors.OKCYAN}[{time.ctime()}] Fetching new events...{Colors.ENDC}")
            events = list(gh.all_events())
            if verbose:
                print(f"{Colors.OKCYAN}[{time.ctime()}] Retrieved {len(events)} events.{Colors.ENDC}")

            if not events:
                time.sleep(POLL_INTERVAL)
                continue

            if last_event_id is None:
                last_event_id = events[0].id

            new_events = [e for e in events if e.id > last_event_id]

            if new_events:
                if verbose:
                    print(f"{Colors.OKGREEN}[{time.ctime()}] Found {len(new_events)} new events to process.{Colors.ENDC}")
                
                for event in reversed(new_events):
                    skip_repo.clear() # Reset skip flag for the new repo
                    try:
                        if event.type == 'PushEvent':
                            repo_info = event.repo
                            if not repo_info or 'name' not in repo_info:
                                continue
                            
                            owner, name = repo_info['name'].split('/', 1)
                            repo = gh.repository(owner, name)

                            if not repo:
                                continue

                            if verbose:
                                print(f"{Colors.HEADER}New PushEvent in: {repo.full_name}{Colors.ENDC}")
                            
                            for commit_data in event.payload.get('commits', []):
                                if skip_repo.is_set(): break
                                
                                commit_sha = commit_data.get('sha')
                                if not commit_sha:
                                    continue

                                if verbose:
                                    print(f"  -> Processing commit {commit_sha[:7]}...")
                                
                                commit = repo.commit(commit_sha)
                                if not commit or not hasattr(commit, 'files'):
                                    continue

                                # --- Stage 1: Parallel Download ---
                                files_to_process = []
                                files_scanned = 0
                                with ThreadPoolExecutor(max_workers=args.cpus * 2) as executor:
                                    future_to_file = {}
                                    for file in commit.files:
                                        if skip_repo.is_set() or files_scanned >= MAX_FILES_PER_REPO:
                                            break
                                        
                                        filename = file.get('filename')
                                        if not filename or not any(filename.endswith(ext) for ext in TARGET_EXTENSIONS):
                                            continue

                                        files_scanned += 1
                                        if file.get('contents_url'):
                                            future_to_file[executor.submit(download_file_content, file.get('contents_url'))] = file

                                    for future in as_completed(future_to_file):
                                        file_meta = future_to_file[future]
                                        content_data = future.result()
                                        if content_data:
                                            files_to_process.append({
                                                "filename": file_meta.get('filename'),
                                                "raw_url": file_meta.get('raw_url'),
                                                "content_data": content_data
                                            })
                                
                                # --- Stage 2: Local Analysis & Queueing for LLM ---
                                for file_data in files_to_process:
                                    decoded_content = base64.b64decode(file_data['content_data']['content']).decode('utf-8', 'ignore')
                                    true_file_size = len(decoded_content)
                                    
                                    if verbose:
                                        if true_file_size < 1024:
                                            size_str = f"{true_file_size} B"
                                        else:
                                            size_str = f"{true_file_size / 1024:.2f} KB"
                                        print(f"    -> Scanning file: {file_data['filename']} ({size_str}) ({Colors.UNDERLINE}{file_data['raw_url']}{Colors.ENDC})")

                                    potential_leaks = analyzer.find_potential_leaks(decoded_content)
                                    
                                    if potential_leaks:
                                        snippets_for_llm = []
                                        for key_type, line_num, match_content in potential_leaks:
                                            snippet = ""
                                            if key_type == "SEED_PHRASE":
                                                snippet = match_content
                                            else:
                                                line = match_content
                                                end = min(len(line), max(0, line.find(line.strip()) - 128) + 256)
                                                snippet = line[max(0, line.find(line.strip()) - 128):end]
                                            
                                            snippets_for_llm.append({
                                                "snippet": snippet, "line_num": line_num, "line": match_content,
                                                "key_type": key_type
                                            })
                                        
                                        llm_analysis_queue.put({
                                            "file_path": file_data['filename'],
                                            "decoded_content": decoded_content,
                                            "raw_url": file_data['raw_url'],
                                            "file_size": true_file_size,
                                            "potential_leaks": snippets_for_llm
                                        })

                                if files_scanned >= MAX_FILES_PER_REPO and verbose:
                                    print(f"  -> {Colors.WARNING}File limit reached for this repo. Skipping remaining files.{Colors.ENDC}")
                                
                                if skip_repo.is_set(): break
                    except (AttributeError, TypeError):
                        if verbose:
                            print(f"{Colors.WARNING}[{time.ctime()}] Skipping malformed event of type {event.type}.{Colors.ENDC}")
                            print(f"  -> Payload: {event.payload}")
                        continue
            else:
                if verbose:
                    print(f"{Colors.OKCYAN}[{time.ctime()}] No new events found.{Colors.ENDC}")

            if new_events:
                last_event_id = new_events[0].id
            
            if verbose:
                print(f"{Colors.OKCYAN}[{time.ctime()}] Waiting for {POLL_INTERVAL} seconds...{Colors.ENDC}")
            time.sleep(POLL_INTERVAL)

        except github3.exceptions.ForbiddenError:
            print("GitHub API rate limit exceeded or token is invalid. Waiting 60 seconds.")
            time.sleep(60)
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scan GitHub for exposed private keys in real-time.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging for detailed, real-time feedback."
    )
    parser.add_argument(
        "--cpus",
        type=int,
        default=os.cpu_count(),
        help="Number of CPU cores (worker threads) to use for parallel processing."
    )
    args = parser.parse_args()

    print_startup_info(args)
    monitor_github_events(args) 