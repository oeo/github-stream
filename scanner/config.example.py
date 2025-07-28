# --- GitHub Configuration ---
# Generate a token here: https://github.com/settings/tokens
# The token needs the `public_repo` scope to read public repositories.
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"
# Poll interval in seconds
POLL_INTERVAL = 10

# --- Scanner Configuration ---
# 'regex_then_llm': Fast. Use regex to find potential keys, then LLM to verify snippet. (Default)
# 'full_file_llm': Slow but more context-aware. Use LLM to analyze the entire file content.
#                  Falls back to 'regex_then_llm' for files that are too large for the model.
SCAN_MODE = "regex_then_llm"

# --- LLM Provider ---
# Choose how the LLM is run.
# - "huggingface": Runs the model directly within the script using the transformers library.
# - "ollama": Connects to a local Ollama server. Requires Ollama to be installed and running. (Default)
LLM_PROVIDER = "ollama"

# --- Hugging Face Configuration (Used if LLM_PROVIDER is "huggingface") ---
MODEL_CONFIGS = {
    "llama3.1_8b": {
        "name": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "max_tokens": 128000
    },
    "phi3_mini_4k": {
        "name": "microsoft/phi-3-mini-4k-instruct",
        "max_tokens": 4096
    }
}
LLM_MODEL_KEY = "llama3.1_8b"
HUGGING_FACE_TOKEN = "YOUR_HUGGING_FACE_TOKEN_HERE"

# --- Ollama Configuration (Used if LLM_PROVIDER is "ollama") ---
OLLAMA_CONFIG = {
    "host": "http://localhost:11434",
    # This model should be available locally via `ollama ls`
    "model": "llama3:8b-instruct-q8_0",
    "max_tokens": 8192 # Llama 3 has an 8k context window
}

# --- Scanner Limiting ---
MAX_FILES_PER_REPO = 100 # The maximum number of files to scan in a single repository 