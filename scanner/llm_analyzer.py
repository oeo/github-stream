import requests
from scanner.config import LLM_PROVIDER

if LLM_PROVIDER == "huggingface":
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    import torch
    from scanner.config import MODEL_CONFIGS, LLM_MODEL_KEY, HUGGING_FACE_TOKEN
else: # ollama
    from scanner.config import OLLAMA_CONFIG

# Define the prompt template for the LLM
PROMPT_TEMPLATE = """
Analyze the following code snippet and classify it as REAL_KEY, TEST_KEY, or NOT_KEY.
If it is a REAL_KEY or TEST_KEY, also identify the cryptocurrency or key type.
Respond with only the classification and the type in parentheses, like "REAL_KEY (Bitcoin WIF)" or "TEST_KEY (Solana)".

- A REAL_KEY is a valid, production-ready cryptocurrency private key or seed phrase.
  - Common formats include Bitcoin (WIF), Solana (Base58), Ripple, Dogecoin, and hex keys (Ethereum, Monero).
  - A seed phrase is typically a list of 12 or 24 words.
- A TEST_KEY is a fake, example, or placeholder key, often found in test files or documentation.
- NOT_KEY is anything else.

---
Here are some examples:

[Example 1]
Content: "const btc_wallet_private_key = 'L5kZp2hG2hZRzps2hG2hZRzps2hG2hZRzps2hG2hZRzps2hG2hZRzps2';"
Classification: REAL_KEY

[Example 2]
Content: "const TEST_API_KEY = '0x12345...';"
Classification: TEST_KEY

[Example 3]
Content: "An Ethereum key looks like `0x[a-f0-9]{{64}}`."
Classification: NOT_KEY

[Example 4]
Content: "example_seed_phrase = 'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about'"
Classification: TEST_KEY
---

Now, classify this content:
Content: {code_snippet}
"""

class LLMAnalyzer:
    def __init__(self, verbose=False):
        self.verbose = verbose
        if LLM_PROVIDER == "huggingface":
            self._init_huggingface()
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
            "options": { "num_predict": 15 } # Increase prediction length for the type
        }
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        return response.json()['response'].strip()

    def classify_snippet(self, snippet):
        prompt = PROMPT_TEMPLATE.format(code_snippet=snippet)
        if LLM_PROVIDER == "huggingface":
            classification = self._classify_with_huggingface(prompt)
        else: # ollama
            classification = self._classify_with_ollama(prompt)
        
        # We will just return the raw classification now, as it's more complex
        return classification

    def classify_file(self, file_content):
        return self.classify_snippet(file_content) 