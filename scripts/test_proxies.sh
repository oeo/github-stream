#!/bin/bash
# This script tests a list of proxies (ss, vless, vmess, trojan, hysteria) for connectivity.

# --- Colors ---
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Check for input file ---
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <proxy_list_file>"
    exit 1
fi

PROXY_FILE=$1

if [ ! -f "$PROXY_FILE" ]; then
    echo -e "${RED}Error: File '$PROXY_FILE' not found.${NC}"
    exit 1
fi

# --- Test Loop ---
echo "Testing proxies from $PROXY_FILE..."
echo "-----------------------------------"

while IFS= read -r proxy_url; do
    echo -n "Testing: $proxy_url ... "
    
    # Use curl with a 10-second timeout to test connectivity to Google via the proxy
    # The --socks5-hostname flag is a common way to use these types of proxies with curl,
    # assuming you have a local client running (like v2ray or clash) that exposes a SOCKS5 port.
    # Note: This is a generic test and might need adjustment based on your local proxy client setup.
    if curl -s --proxy "$proxy_url" --connect-timeout 10 https://www.google.com > /dev/null; then
        echo -e "${GREEN}SUCCESS${NC}"
    else
        echo -e "${RED}FAILURE${NC}"
    fi
done < "$PROXY_FILE"

echo "-----------------------------------"
echo "Proxy test complete." 