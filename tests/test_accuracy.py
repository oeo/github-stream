import os
import sys
import glob

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.llm_analyzer import LLMAnalyzer
from scanner.main import Colors
from scanner.config import LLM_PROVIDER, HUGGING_FACE_TOKEN

def run_accuracy_test():
    """
    Tests the accuracy of the LLMAnalyzer by running it against a set of sample files.
    """
    analyzer = LLMAnalyzer(verbose=True)
    
    if LLM_PROVIDER == "huggingface":
        if HUGGING_FACE_TOKEN == "YOUR_HUGGING_FACE_TOKEN_HERE" or not HUGGING_FACE_TOKEN:
            print(f"{Colors.FAIL}Error: Hugging Face token is not configured in scanner/config.py.{Colors.ENDC}")
            return

    test_cases = [
        ("tests/samples/real_keys/solana_key.txt", "REAL_KEY"),
        ("tests/samples/real_keys/config_with_real_key.js", "REAL_KEY"),
        ("tests/samples/real_keys/ethereum_key.env", "REAL_KEY"),
        ("tests/samples/real_keys/litecoin_key.txt", "REAL_KEY"),
        ("tests/samples/real_keys/multiline_seed_phrase.md", "REAL_KEY"),
        ("tests/samples/real_keys/real_seed_phrase.txt", "REAL_KEY"),
        ("tests/samples/test_keys/unit_test_with_fake_seed.py", "TEST_KEY"),
        ("tests/samples/test_keys/example_keys.txt", "TEST_KEY"),
        ("tests/samples/no_keys/documentation_about_keys.md", "NOT_KEY"),
        ("tests/samples/no_keys/safe_code.py", "NOT_KEY"),
        ("tests/samples/no_keys/normal_long_sentence.txt", "NOT_KEY"),
    ]

    correct_predictions = 0
    total_predictions = len(test_cases)

    print(f"\n{Colors.HEADER}--- Running LLM Accuracy Test ---{Colors.ENDC}")
    print(f"Found {total_predictions} test cases.")

    for filepath, expected in test_cases:
        with open(filepath, 'r') as f:
            content = f.read()
        
        print(f"\n-> Testing: {filepath} (Expected contains: {expected})")
        classification = analyzer.classify_file(content)
        
        if expected in classification:
            print(f"  {Colors.OKGREEN}Correct!{Colors.ENDC} (Got: {classification})")
            correct_predictions += 1
        else:
            print(f"  {Colors.FAIL}Incorrect!{Colors.ENDC} (Got: {classification}, Expected contains: {expected})")

    accuracy = (correct_predictions / total_predictions) * 100
    print(f"\n{Colors.HEADER}--- Test Complete ---{Colors.ENDC}")
    print(f"Accuracy: {accuracy:.2f}% ({correct_predictions}/{total_predictions} correct)")

if __name__ == "__main__":
    run_accuracy_test() 