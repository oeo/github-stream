import requests
from scanner.config import LLM_PROVIDER

if LLM_PROVIDER == "huggingface":
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    import torch
    from scanner.config import MODEL_CONFIGS, LLM_MODEL_KEY, HUGGING_FACE_TOKEN
elif LLM_PROVIDER == "openrouter":
    from scanner.config import OPENROUTER_CONFIG
else: # ollama
    from scanner.config import OLLAMA_CONFIG

# Define the prompt template for the LLM
PROMPT_TEMPLATE = """
Analyze the following code snippet and classify it as REAL_KEY, TEST_KEY, or NOT_KEY.
If it is a REAL_KEY or TEST_KEY, also identify the specific cryptocurrency or key type.
Your response MUST be ONLY the classification and the type in parentheses. Do not include any other text, explanations, or formatting.

---
**KEY FORMAT GUIDE**

- **Bitcoin WIF (Compressed):** Starts with 'K' or 'L', 52 chars. Ex: L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1
- **Bitcoin WIF (Uncompressed):** Starts with '5', 51 chars. Ex: 5KJvsngHeMpm884wtkJNzQGaCErckhHJBGFsvd3VyK5qMZXj3hS
- **Bitcoin BIP32 Extended:** Starts with 'xprv', 111 chars.
- **Ethereum & EVM Hex Key:** 64 hex chars, often with '0x' prefix.
- **Solana Keypair:** 88 Base58 chars.
- **Ripple Secret:** Starts with 's', 29 chars. Ex: sp6JS7f14BuwFY8Mw6bTtLKWauoUs
- **Litecoin WIF:** Starts with '6' or 'T'.
- **Seed Phrase:** A list of 12 or 24 words.

---
**EXAMPLES**

[Example 1]
Content: "const btc_wallet_private_key = 'L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1';"
Classification: REAL_KEY (Bitcoin WIF)

[Example 2]
Content: "solana_test_key = '2gFkWRQgE8Z7Hq3K3rXwJ6yXvJdVpXMN6fTbeFhP3QyAqCNvY7ZDqrXnjBm9M2kmWEj1mpfNBZqWYvdWyWWHGfaV';"
Classification: TEST_KEY (Solana)

[Example 3]
Content: "An Ethereum key looks like `0x[a-f0-9]{{64}}`."
Classification: NOT_KEY

[Example 4]
Content: "witch collapse practice feed shame open despair creek road again ice least"
Classification: REAL_KEY (Seed Phrase)
---

Now, classify this content:
Content: {code_snippet}
"""

class LLMAnalyzer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        if LLM_PROVIDER == "huggingface":
            self._init_huggingface()
        elif LLM_PROVIDER == "openrouter":
            self._init_openrouter()
        elif LLM_PROVIDER == "ollama":
            self._init_ollama()
        
        if self.verbose:
            print(f"LLM Analyzer initialized using {LLM_PROVIDER} provider.")

    def _init_huggingface(self):
        model_config = MODEL_CONFIGS[LLM_MODEL_KEY]
        model_name = model_config["name"]
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, token=HUGGING_FACE_TOKEN)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            token=HUGGING_FACE_TOKEN,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        self.pipe = pipeline("text-generation", model=self.model, tokenizer=self.tokenizer)

    def _init_ollama(self):
        # Nothing to do here, we just need the requests library.
        # We can do a quick check to see if the server is running.
        try:
            requests.get(OLLAMA_CONFIG['host'])
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to Ollama server at {OLLAMA_CONFIG['host']}.")
            print("Please ensure Ollama is running.")
            exit(1)

    def _init_openrouter(self):
        if not OPENROUTER_CONFIG.get('api_key'):
            print("Error: OpenRouter API key is missing.")
            print("Set the OPENROUTER_API_KEY env var or fill in api_key in scanner/config.py.")
            exit(1)

    def _classify_with_huggingface(self, prompt):
        generation_args = {
            "max_new_tokens": 15,
            "return_full_text": False,
            "do_sample": True,
            "temperature": 0.01,  # Near-zero temperature for deterministic output
            "top_k": 1            # Only consider the most likely token
        }
        output = self.pipe(prompt, **generation_args)
        return output[0]['generated_text'].strip()

    def _classify_with_ollama(self, prompt):
        api_url = f"{OLLAMA_CONFIG['host']}/api/generate"
        payload = {
            "model": OLLAMA_CONFIG['model'],
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 15,
                "temperature": 0
            }
        }
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        return response.json()['response'].strip()

    def _classify_with_openrouter(self, prompt):
        api_url = f"{OPENROUTER_CONFIG['host']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENROUTER_CONFIG['model'],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 15,
        }
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()

    def classify_snippet(self, snippet):
        prompt = PROMPT_TEMPLATE.format(code_snippet=snippet)
        if LLM_PROVIDER == "huggingface":
            classification = self._classify_with_huggingface(prompt)
        elif LLM_PROVIDER == "openrouter":
            classification = self._classify_with_openrouter(prompt)
        else: # ollama
            classification = self._classify_with_ollama(prompt)
        
        # We will just return the raw classification now, as it's more complex
        return classification

    def classify_file(self, file_content):
        return self.classify_snippet(file_content) 