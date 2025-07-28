import re

class Analyzer:
    def __init__(self):
        # A generic regex to find a wide range of potential keys and seed phrases.
        # - Catches long hex strings (e.g., Ethereum)
        # - Catches Base58-like strings (e.g., Bitcoin, Solana)
        # - Catches sequences of 12 or more words (seed phrases)
        self.generic_pattern = re.compile(
            r'([a-fA-F0-9]{64})|([5KL1-9A-HJ-NP-Za-km-z]{44,52})|(\b[a-zA-Z]+\b(\s+\b[a-zA-Z]+\b){11,})'
        )

    def find_potential_leaks(self, content):
        """
        Scans content for potential leaks using a generic pattern.
        """
        leaks = []
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if self.generic_pattern.search(line):
                leaks.append((i + 1, line))
        
        return leaks 