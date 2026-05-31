#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enhanced multi-token github scanner with parallel processing.
"""

import os
import re
import time
import github3
import base64
import requests
import argparse
import fnmatch
from datetime import datetime
from scanner.analyzer import Analyzer
from scanner.llm_analyzer import LLMAnalyzer
from scanner.config import (
    TARGET_EXTENSIONS, GITHUB_TOKEN, GITHUB_TOKENS, POLL_INTERVAL, MAX_FILE_SIZE, MIN_FILE_SIZE,
    SCAN_MODE, LLM_PROVIDER, MODEL_CONFIGS, LLM_MODEL_KEY, OLLAMA_CONFIG,
    MAX_FILES_PER_REPO, EXCLUDED_FILES, EXCLUDED_PATTERNS
)
from scanner.token_manager import TokenManager
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import signal

def signal_handler(sig, frame):
    print(f"Caught signal {sig}")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# global variables
skip_repo = threading.Event()
llm_analysis_queue = Queue()

# key types confirmed by regex alone - logged directly, bypassing LLM verification
DIRECT_DETECTION_KEYS = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"}

class Colors:
    """ansi color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# configure logging
import logging
logging.basicConfig(
    filename='scanner/logs/detections.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logging.getLogger("github3").setLevel(logging.WARNING)

# directory for saving detected files
LEAKS_DIR = "detected_leaks"
if not os.path.exists(LEAKS_DIR):
    os.makedirs(LEAKS_DIR)

def log_detection(key_type, file_path, line_number, match, raw_url, file_size):
    """logs a detected key to the console and a file."""
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
    """saves the content of a file that contains a detected key."""
    try:
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
            line_preview = (detection['line'][:75] + '...') if len(detection['line']) > 75 else detection['line']
            header += f"# - Line {detection['line_num']}: {detection['classification']} -> \"{line_preview}\"\n"
        header += "# --- END METADATA ---\n\n"

        full_content_with_header = header + content

        with open(leak_file_path, 'w', encoding='utf-8') as f:
            f.write(full_content_with_header)

        print(f"  -> {Colors.FAIL}Saved leaked file with metadata to: {leak_file_path}{Colors.ENDC}")
    except Exception as e:
        print(f"  -> {Colors.FAIL}Error saving leaked file {file_path}: {e}{Colors.ENDC}")

def llm_worker(llm_analyzer, verbose=False):
    """worker thread that consumes files from a queue and performs llm analysis."""
    while True:
        file_to_process = llm_analysis_queue.get()
        if file_to_process is None:
            break

        file_path = file_to_process['file_path']
        decoded_content = file_to_process['decoded_content']
        raw_url = file_to_process['raw_url']
        file_size = file_to_process['file_size']
        potential_leaks = file_to_process['potential_leaks']

        real_key_detections = []

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

def user_input_thread():
    """thread to listen for the 's' key to skip the current repository."""
    while True:
        if sys.stdin.isatty():
            user_input = input()
            if user_input.strip().lower() == 's':
                print(f"{Colors.WARNING}Skip command received. Finishing current file and skipping rest of repo...{Colors.ENDC}")
                skip_repo.set()

def scanner_worker(token_manager, analyzer, event_queue, verbose, worker_id):
    """worker thread that processes events using a specific token."""
    while True:
        event_data = event_queue.get()
        if event_data is None:
            break

        token, token_index = token_manager.get_next_token()
        if not token:
            print(f"[Worker {worker_id}] No healthy tokens available, skipping event")
            event_queue.task_done()
            continue

        try:
            gh = github3.login(token=token)
            process_event(gh, event_data, analyzer, verbose, token_manager, token, worker_id)
            token_manager.mark_token_success(token)
        except Exception as e:
            token_manager.mark_token_error(token, str(e))
            if verbose:
                print(f"[Worker {worker_id}] Error processing event: {e}")
        finally:
            event_queue.task_done()

def process_event(gh, event_data, analyzer, verbose, token_manager, token, worker_id):
    """process a single github event."""
    repo_name = event_data['repo_name']
    commits = event_data['commits']

    if verbose:
        print(f"{Colors.HEADER}[Worker {worker_id}] Processing {repo_name}{Colors.ENDC}")

    owner, name = repo_name.split('/')

    try:
        repo = gh.repository(owner, name)
        if not repo:
            return

        for commit_sha in commits:
            if skip_repo.is_set():
                skip_repo.clear()
                break

            if verbose:
                print(f"  -> [Worker {worker_id}] Commit {commit_sha[:7]}...")

            try:
                commit = repo.commit(commit_sha)
                if not commit or not commit.files:
                    continue

                files_scanned = 0
                files_to_process = []

                # download files in parallel
                with ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_file = {}

                    for file in commit.files:
                        if skip_repo.is_set() or files_scanned >= MAX_FILES_PER_REPO:
                            break

                        filename = file.get('filename')
                        if not filename:
                            continue

                        # apply filtering logic
                        base_filename = filename.split('/')[-1] if '/' in filename else filename

                        if base_filename in EXCLUDED_FILES:
                            continue

                        if any(fnmatch.fnmatch(base_filename, pattern) for pattern in EXCLUDED_PATTERNS):
                            continue

                        is_dotfile = '/' in filename and filename.split('/')[-1].startswith('.') or filename.startswith('.')

                        if not (is_dotfile or any(filename.endswith(ext) for ext in TARGET_EXTENSIONS)):
                            continue

                        files_scanned += 1
                        if file.get('contents_url'):
                            headers = {'Authorization': f'token {token}'}
                            future_to_file[executor.submit(
                                requests.get,
                                file.get('contents_url'),
                                headers=headers
                            )] = file

                    for future in as_completed(future_to_file):
                        file_meta = future_to_file[future]
                        try:
                            response = future.result()
                            if response.status_code == 200:
                                content_data = response.json()
                                files_to_process.append({
                                    "filename": file_meta.get('filename'),
                                    "raw_url": file_meta.get('raw_url'),
                                    "content_data": content_data
                                })

                                # update rate limits
                                if 'X-RateLimit-Remaining' in response.headers:
                                    remaining = int(response.headers['X-RateLimit-Remaining'])
                                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
                                    token_manager.update_token_limits(token, remaining, reset_time)
                        except Exception as e:
                            if verbose:
                                print(f"Error downloading {file_meta.get('filename')}: {e}")

                # process downloaded files
                for file_data in files_to_process:
                    try:
                        decoded_content = base64.b64decode(file_data['content_data']['content']).decode('utf-8', 'ignore')
                        true_file_size = len(decoded_content)

                        if true_file_size < MIN_FILE_SIZE or true_file_size > MAX_FILE_SIZE:
                            continue

                        if verbose:
                            size_str = f"{true_file_size} B" if true_file_size < 1024 else f"{true_file_size / 1024:.2f} KB"
                            print(f"    -> Scanning: {file_data['filename']} ({size_str})")
                            print(f"       URL: {Colors.UNDERLINE}{file_data['raw_url']}{Colors.ENDC}")

                        potential_leaks = analyzer.find_potential_leaks(decoded_content)

                        if potential_leaks:
                            snippets = []
                            direct_detections = []
                            for key_type, line_num, line in potential_leaks:
                                if key_type in DIRECT_DETECTION_KEYS:
                                    direct_detections.append({
                                        "classification": key_type,
                                        "line_num": line_num,
                                        "line": line
                                    })
                                    log_detection(key_type, file_data['filename'], line_num, line.strip(), file_data['raw_url'], true_file_size)
                                elif key_type != "SEED_PHRASE":
                                    snippets.append({
                                        'snippet': line.strip(),
                                        'line_num': line_num,
                                        'line': line
                                    })

                            if direct_detections:
                                save_leaked_file(file_data['filename'], decoded_content, direct_detections, file_data['raw_url'], true_file_size)

                            if snippets:
                                llm_analysis_queue.put({
                                    'file_path': file_data['filename'],
                                    'decoded_content': decoded_content,
                                    'raw_url': file_data['raw_url'],
                                    'file_size': true_file_size,
                                    'potential_leaks': snippets
                                })
                    except Exception as e:
                        if verbose:
                            print(f"Error processing file: {e}")

            except Exception as e:
                if verbose:
                    print(f"Error processing commit {commit_sha}: {e}")

    except Exception as e:
        if verbose:
            print(f"Error accessing repository {repo_name}: {e}")

def monitor_github_events(args):
    """monitors github for new pushevents and scans with multiple tokens."""
    verbose = args.verbose

    # use github_tokens if available, otherwise fall back to single token
    tokens = GITHUB_TOKENS if GITHUB_TOKENS else [GITHUB_TOKEN]

    if not tokens or tokens[0] == "YOUR_NEW_GITHUB_TOKEN_HERE":
        print("Please add your GitHub token(s) to scanner/config.py")
        return

    # initialize token manager
    token_manager = TokenManager(tokens, verbose=verbose)

    print(f"{Colors.HEADER}--- GitHub Multi-Token Scanner ---{Colors.ENDC}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Using {len(tokens)} token(s)")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Healthy tokens: {token_manager.get_healthy_token_count()}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Total rate limit: {token_manager.get_total_remaining_requests()} requests")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Worker threads: {args.cpus}")
    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Max files per repo: {MAX_FILES_PER_REPO}")

    # initialize analyzers
    analyzer = Analyzer()
    llm_analyzer = LLMAnalyzer(verbose=verbose)

    # start llm worker threads
    num_llm_workers = args.cpus
    llm_workers = []
    for _ in range(num_llm_workers):
        worker = threading.Thread(target=llm_worker, args=(llm_analyzer, verbose), daemon=True)
        worker.start()
        llm_workers.append(worker)

    # create event queue for parallel processing
    event_queue = Queue(maxsize=100)

    # start scanner worker threads (one per healthy token, max 4)
    num_scanner_workers = min(token_manager.get_healthy_token_count(), 4)
    scanner_workers = []
    for i in range(num_scanner_workers):
        worker = threading.Thread(
            target=scanner_worker,
            args=(token_manager, analyzer, event_queue, verbose, i+1),
            daemon=True
        )
        worker.start()
        scanner_workers.append(worker)

    print(f"[{Colors.OKBLUE}INFO{Colors.ENDC}] Started {num_scanner_workers} scanner workers")
    print(f"{Colors.HEADER}---------------------------{Colors.ENDC}")

    # use first token for fetching events
    event_token, _ = token_manager.get_next_token()
    if not event_token:
        print("No healthy tokens available!")
        return

    gh = github3.login(token=event_token)
    last_event_id = None

    if verbose:
        print("Monitoring GitHub for new commits... (Press 's' then Enter to skip a repository)")
    else:
        print("Monitoring GitHub for new commits...")

    # start user input thread
    input_thread = threading.Thread(target=user_input_thread, daemon=True)
    input_thread.start()

    # periodically print token status
    last_status_time = time.time()

    while True:
        try:
            # print token status every 5 minutes
            if time.time() - last_status_time > 300:
                if verbose:
                    token_manager.print_status()
                last_status_time = time.time()

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
                    try:
                        if event.type == 'PushEvent':
                            repo_info = event.repo
                            if not repo_info or 'name' not in repo_info:
                                continue

                            repo_name = repo_info['name']
                            commits = [c.get('sha') for c in event.payload.get('commits', []) if c.get('sha')]

                            if commits:
                                # queue the event for processing by workers
                                event_data = {
                                    'repo_name': repo_name,
                                    'commits': commits
                                }
                                event_queue.put(event_data)

                    except Exception as e:
                        if verbose:
                            print(f"Error processing event: {e}")

                last_event_id = new_events[-1].id

            time.sleep(POLL_INTERVAL)

        except github3.exceptions.ForbiddenError:
            print("GitHub API rate limit exceeded. Waiting 60 seconds...")
            time.sleep(60)
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(POLL_INTERVAL)

def main():
    parser = argparse.ArgumentParser(description='Monitor GitHub for exposed secrets in real-time')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-c', '--cpus', type=int, default=4, help='Number of CPU cores to use (default: 4)')

    args = parser.parse_args()

    try:
        monitor_github_events(args)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)

if __name__ == "__main__":
    main()
