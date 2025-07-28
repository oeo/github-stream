#!/bin/bash
# This script clears all logs and detected leak files.

echo "Clearing log files..."
rm -f scanner/logs/*.log

echo "Clearing detected leak files..."
rm -f detected_leaks/*

echo "Done." 