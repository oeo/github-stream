# Real-Time Cryptocurrency Private Key Scanner

This project is an automated detection and notification system designed to find exposed cryptocurrency private keys and seed phrases in public GitHub repositories in real-time. It uses a multi-stage pipeline, combining fast initial scanning with powerful Large Language Model (LLM) analysis to ensure high accuracy and performance.

## Features

- **Real-Time Monitoring:** Scans new commits from the public GitHub Events API as they happen.
- **Intelligent Analysis:** Uses a fast local analyzer to find potential leaks, which are then verified by a powerful LLM for high accuracy.
- **Flexible LLM Backend:** Supports both local LLMs via Ollama and direct model loading via the Hugging Face `transformers` library.
- **Configurable:** Easily switch between different LLMs, scanning modes, and providers through a simple configuration file.
- **Interactive:** Allows you to skip repositories on the fly and limits the number of files scanned per repository to avoid getting bogged down.
- **Actionable Output:** Provides clear, color-coded logs and saves the full content of any detected leak to a local directory with a detailed metadata header for easy review.
- **Comprehensive Test Suite:** Includes an accuracy test suite to verify the performance of the LLM and the detection logic.

## Architecture

The scanner operates on a fully parallel, multi-stage pipeline for maximum efficiency:

1.  **Event Polling:** The main thread continuously polls the GitHub Events API for new commits.
2.  **Parallel Download:** For each commit, all relevant files (based on extension) are downloaded in parallel.
3.  **Local Analysis & Queueing:** The downloaded files are analyzed by a fast local scanner. Any files with potential leaks are placed into a queue for the LLM workers.
4.  **Parallel LLM Analysis:** A pool of background worker threads consumes files from the queue, sending all potential leaks from each file to the LLM for analysis in parallel.
5.  **Logging & Saving:** If the LLM confirms a `REAL_KEY`, the finding is logged, and the full file is saved to the `detected_leaks` directory for review.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    cd github-stream
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure the scanner:**
    -   Create a copy of the example configuration file:
        ```bash
        cp scanner/config.example.py scanner/config.py
        ```
    -   Open `scanner/config.py` in your editor and add your **GitHub Personal Access Token**. A token with the `public_repo` scope is required.

4.  **Set up your LLM Provider:**
    -   **Ollama (Recommended):**
        -   Install Ollama from [ollama.com](https://ollama.com).
        -   Download the model you want to use (the default is `llama3:8b-instruct-q8_0`):
            ```bash
            ollama run llama3:8b-instruct-q8_0
            ```
        -   Ensure the `LLM_PROVIDER` in your `config.py` is set to `"ollama"`.
    -   **Hugging Face:**
        -   Ensure the `LLM_PROVIDER` in your `config.py` is set to `"huggingface"`.
        -   Add your **Hugging Face Access Token** to `config.py`. This is required for gated models like Llama 3.

## Usage

-   **Run the scanner:**
    ```bash
    python3.9 -m scanner.main
    ```
-   **Run in verbose mode** for detailed logging:
    ```bash
    python3.9 -m scanner.main --verbose
    ```
-   **Run the accuracy test** to verify the LLM's performance:
    ```bash
    python3.9 tests/test_accuracy.py
    ```

While the scanner is running, you can press `s` followed by `Enter` to skip the rest of the files in the current repository and move on to the next one.

