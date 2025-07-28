import argparse
import re
from urllib.parse import urlparse, parse_qs

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

def parse_proxy_url(url):
    """Parses a proxy URL and extracts its components."""
    try:
        protocol = url.split("://")[0]
        parsed = urlparse(url)
        
        return {
            "protocol": protocol,
            "username": parsed.username,
            "hostname": parsed.hostname,
            "port": parsed.port,
            "params": parse_qs(parsed.query),
            "fragment": parsed.fragment,
        }
    except Exception as e:
        return {"error": str(e)}

def main(proxy_file):
    """
    Reads a file of proxy URLs, parses them, and prints the results.
    """
    print(f"{Colors.HEADER}--- Parsing Proxies from {proxy_file} ---{Colors.ENDC}")

    with open(proxy_file, 'r') as f:
        for line in f:
            url = line.strip()
            if not url:
                continue

            parsed_data = parse_proxy_url(url)

            if "error" in parsed_data:
                print(f"\n{Colors.FAIL}[-] Error parsing URL: {url}{Colors.ENDC}")
                print(f"  -> {parsed_data['error']}")
            else:
                print(f"\n{Colors.OKGREEN}[+] Parsed {parsed_data['protocol'].upper()} Proxy:{Colors.ENDC}")
                print(f"  - Host: {Colors.BOLD}{parsed_data['hostname']}:{parsed_data['port']}{Colors.ENDC}")
                if parsed_data['username']:
                    print(f"  - User: {parsed_data['username']}")
                if parsed_data['params']:
                    print("  - Parameters:")
                    for key, value in parsed_data['params'].items():
                        print(f"    - {key}: {value[0]}")
                if parsed_data['fragment']:
                    print(f"  - Name: {parsed_data['fragment']}")

    print(f"\n{Colors.HEADER}--- Parsing Complete ---{Colors.ENDC}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse and validate a list of proxy URLs.")
    parser.add_argument("proxy_file", help="The path to the file containing proxy URLs.")
    args = parser.parse_args()
    
    main(args.proxy_file) 