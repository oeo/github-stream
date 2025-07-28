this project is an automated detection and notification system designed to find exposed cryptocurrency private keys and seed phrases in public github repositories in real-time. it uses a multi-stage pipeline, combining fast initial scanning with powerful large language model (llm) analysis to ensure high accuracy and performance.

## features

- **real-time monitoring:** scans new commits from the public github events api as they happen.
- **intelligent analysis:** uses a fast local analyzer to find potential leaks, which are then verified by a powerful llm for high accuracy.
- **flexible llm backend:** supports both local llms via ollama and direct model loading via the hugging face `transformers` library.
- **configurable:** easily switch between different llms, scanning modes, and providers through a simple configuration file.
- **interactive:** allows you to skip repositories on the fly and limits the number of files scanned per repository to avoid getting bogged down.
- **actionable output:** provides clear, color-coded logs and saves the full content of any detected leak to a local directory with a detailed metadata header for easy review.
- **comprehensive test suite:** includes an accuracy test suite to verify the performance of the llm and the detection logic.

## about 

the scanner operates on a fully parallel, multi-stage pipeline for maximum efficiency:

1.  **event polling:** the main thread continuously polls the github events api for new commits.
2.  **parallel download:** for each commit, all relevant files (based on extension) are downloaded in parallel.
3.  **local analysis & queueing:** the downloaded files are analyzed by a fast local scanner. any files with potential leaks are placed into a queue for the llm workers.
4.  **parallel llm analysis:** a pool of background worker threads consumes files from the queue, sending all potential leaks from each file to the llm for analysis in parallel.
5.  **logging & saving:** if the llm confirms a `real_key`, the finding is logged, and the full file is saved to the `detected_leaks` directory for review.

## getting started 

1.  **clone the repository:**
    ```bash
    git clone <repository_url>
    cd github-stream
    ```

2.  **install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **configure the scanner:**
    -   create a copy of the example configuration file:
        ```bash
        cp scanner/config.example.py scanner/config.py
        ```
    -   open `scanner/config.py` in your editor and add your **github personal access token**. a token with the `public_repo` scope is required.

4.  **set up your llm provider:**
    -   **ollama (recommended):**
        -   install ollama from [ollama.com](https://ollama.com).
        -   download the model you want to use (the default is `llama3:8b-instruct-q8_0`):
            ```bash
            ollama run llama3:8b-instruct-q8_0
            ```
        -   ensure the `LLM_PROVIDER` in your `config.py` is set to `"ollama"`.
    -   **hugging face:**
        -   ensure the `LLM_PROVIDER` in your `config.py` is set to `"huggingface"`.
        -   add your **hugging face access token** to `config.py`. this is required for gated models like llama 3.

## usage

-   **run the scanner:**
    ```bash
    python3.9 -m scanner.main
    ```
-   **run in verbose mode** for detailed logging:
    ```bash
    python3.9 -m scanner.main --verbose
    ```
-   **run the accuracy test** to verify the llm's performance:
    ```bash
    python3.9 tests/test_accuracy.py
    ```

while the scanner is running, you can press `s` followed by `enter` to skip the rest of the files in the current repository and move on to the next one. 