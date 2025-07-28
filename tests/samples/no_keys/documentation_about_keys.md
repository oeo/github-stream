# API Key Security Guide

This document outlines the best practices for handling API keys and other sensitive credentials within our system.

## Key Formats

It is important to understand the format of the keys you are working with. For example:

- An Ethereum private key is a 64-character hexadecimal string, often prefixed with `0x`. For example: `0x[a-fA-F0-9]{64}`.
- A Bitcoin private key in WIF format is a 52-character base58 string, like `[5KL][1-9A-HJ-NP-Za-km-z]{51}`.

These examples are for educational purposes only. **Never commit real keys to the repository.** 