#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
token manager for handling multiple github tokens with rotation and health monitoring.
"""

import time
import threading
import requests
from collections import deque
from datetime import datetime, timedelta

class TokenManager:
    """manages multiple github tokens with rotation and rate limit tracking."""
    
    def __init__(self, tokens, verbose=False):
        """
        initialize token manager with a list of tokens.
        
        args:
            tokens: list of github personal access tokens
            verbose: whether to print debug information
        """
        if not tokens:
            raise ValueError("at least one token is required")
        
        self.tokens = tokens
        self.verbose = verbose
        self.token_stats = {}
        self.lock = threading.Lock()
        
        # initialize stats for each token
        for token in tokens:
            self.token_stats[token] = {
                'requests_made': 0,
                'requests_remaining': 5000,
                'reset_time': datetime.now() + timedelta(hours=1),
                'is_healthy': True,
                'last_error': None,
                'consecutive_errors': 0
            }
        
        # create a queue for round-robin rotation
        self.token_queue = deque(tokens)
        self.last_used_index = -1
        
        # check initial token health
        self._check_all_tokens_health()
    
    def get_next_token(self):
        """
        get the next available token using round-robin rotation.
        skips unhealthy tokens and returns the best available token.
        
        returns:
            tuple of (token, index) or (None, -1) if no tokens available
        """
        with self.lock:
            attempts = 0
            best_token = None
            best_remaining = 0
            
            # always rotate the queue to ensure round-robin
            self.token_queue.rotate(-1)
            
            while attempts < len(self.tokens):
                # get current token from front of queue
                token = self.token_queue[attempts]
                attempts += 1
                
                stats = self.token_stats[token]
                
                # check if reset time has passed for exhausted tokens
                if stats['requests_remaining'] <= 10 and datetime.now() >= stats['reset_time']:
                    # reset the counter
                    stats['requests_remaining'] = 5000
                    stats['reset_time'] = datetime.now() + timedelta(hours=1)
                    stats['is_healthy'] = True
                    if self.verbose:
                        token_index = self.tokens.index(token)
                        print(f"[TokenManager] Token #{token_index + 1} reset! Now has 5000 requests")
                
                # skip unhealthy tokens or exhausted tokens
                if not stats['is_healthy'] or stats['requests_remaining'] <= 10:
                    # track best available token even if low on requests
                    if stats['is_healthy'] and stats['requests_remaining'] > best_remaining:
                        best_token = token
                        best_remaining = stats['requests_remaining']
                    continue
                
                # found a good token with sufficient requests
                stats['requests_made'] += 1
                stats['requests_remaining'] = max(0, stats['requests_remaining'] - 1)
                
                if self.verbose:
                    token_index = self.tokens.index(token)
                    print(f"[TokenManager] Using token #{token_index + 1} "
                          f"(remaining: {stats['requests_remaining']})")
                
                return token, self.tokens.index(token)
            
            # use best available token even if low on requests
            if best_token:
                stats = self.token_stats[best_token]
                stats['requests_made'] += 1
                stats['requests_remaining'] = max(0, stats['requests_remaining'] - 1)
                if self.verbose:
                    token_index = self.tokens.index(best_token)
                    print(f"[TokenManager] WARNING: Using low-limit token #{token_index + 1} "
                          f"(only {stats['requests_remaining']} remaining)")
                return best_token, self.tokens.index(best_token)
            
            # no tokens available at all
            if self.verbose:
                print("[TokenManager] ERROR: All tokens exhausted!")
            return None, -1
    
    def update_token_limits(self, token, remaining, reset_time):
        """
        update rate limit information for a token based on api response headers.
        
        args:
            token: the token to update
            remaining: remaining requests from x-ratelimit-remaining header
            reset_time: reset timestamp from x-ratelimit-reset header
        """
        with self.lock:
            if token in self.token_stats:
                stats = self.token_stats[token]
                stats['requests_remaining'] = remaining
                stats['reset_time'] = datetime.fromtimestamp(reset_time)
                
                if self.verbose and remaining < 100:
                    print(f"[TokenManager] Warning: Token has only {remaining} requests left")
    
    def mark_token_error(self, token, error_msg):
        """
        mark that a token encountered an error.
        
        args:
            token: the token that failed
            error_msg: error message
        """
        with self.lock:
            if token in self.token_stats:
                stats = self.token_stats[token]
                stats['last_error'] = error_msg
                stats['consecutive_errors'] += 1
                
                # mark as unhealthy after 3 consecutive errors
                if stats['consecutive_errors'] >= 3:
                    stats['is_healthy'] = False
                    if self.verbose:
                        print(f"[TokenManager] Token marked unhealthy after {stats['consecutive_errors']} errors")
    
    def mark_token_success(self, token):
        """
        mark that a token request succeeded.
        
        args:
            token: the token that succeeded
        """
        with self.lock:
            if token in self.token_stats:
                stats = self.token_stats[token]
                stats['consecutive_errors'] = 0
                stats['last_error'] = None
                # re-enable previously unhealthy tokens
                if not stats['is_healthy']:
                    stats['is_healthy'] = True
                    if self.verbose:
                        print("[TokenManager] Token recovered and marked healthy")
    
    def _check_all_tokens_health(self):
        """check the health of all tokens at startup."""
        if self.verbose:
            print(f"[TokenManager] Checking health of {len(self.tokens)} token(s)...")
        
        for i, token in enumerate(self.tokens):
            try:
                headers = {'Authorization': f'token {token}'}
                response = requests.get('https://api.github.com/rate_limit', headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    core_limits = data.get('rate', {})
                    remaining = core_limits.get('remaining', 0)
                    limit = core_limits.get('limit', 5000)
                    reset_time = core_limits.get('reset', time.time() + 3600)
                    
                    self.token_stats[token]['requests_remaining'] = remaining
                    self.token_stats[token]['reset_time'] = datetime.fromtimestamp(reset_time)
                    self.token_stats[token]['is_healthy'] = True if remaining > 0 else False
                    
                    reset_in = (datetime.fromtimestamp(reset_time) - datetime.now()).total_seconds() / 60
                    
                    if self.verbose:
                        print(f"  Token #{i+1}: {'✓ Healthy' if remaining > 0 else '✗ Exhausted'}")
                        print(f"    Remaining: {remaining}/{limit} requests")
                        print(f"    Resets in: {reset_in:.1f} minutes")
                else:
                    self.token_stats[token]['is_healthy'] = False
                    if self.verbose:
                        print(f"  Token #{i+1}: ✗ Unhealthy (HTTP {response.status_code})")
            except Exception as e:
                self.token_stats[token]['is_healthy'] = False
                if self.verbose:
                    print(f"  Token #{i+1}: ✗ Error checking health: {e}")
    
    def get_healthy_token_count(self):
        """get the number of currently healthy tokens."""
        with self.lock:
            return sum(1 for stats in self.token_stats.values() if stats['is_healthy'])
    
    def get_total_remaining_requests(self):
        """get the total remaining requests across all healthy tokens."""
        with self.lock:
            return sum(stats['requests_remaining'] 
                      for stats in self.token_stats.values() 
                      if stats['is_healthy'])
    
    def print_status(self):
        """print current status of all tokens."""
        with self.lock:
            print("\n[TokenManager] Status Report:")
            print("-" * 50)
            
            total_limit = 0
            for i, token in enumerate(self.tokens):
                stats = self.token_stats[token]
                
                # check for reset
                if stats['requests_remaining'] <= 10 and datetime.now() >= stats['reset_time']:
                    stats['requests_remaining'] = 5000
                    stats['is_healthy'] = True
                
                status = "✓ Healthy" if stats['is_healthy'] else "✗ Exhausted" if stats['requests_remaining'] == 0 else "⚠ Low"
                reset_in = (stats['reset_time'] - datetime.now()).total_seconds() / 60
                
                print(f"Token #{i+1}: {status}")
                print(f"  Requests made this session: {stats['requests_made']}")
                print(f"  Requests remaining: {stats['requests_remaining']}/5000")
                
                if reset_in > 0:
                    print(f"  Resets in: {reset_in:.1f} minutes ({stats['reset_time'].strftime('%H:%M:%S')})")
                else:
                    print(f"  Ready to reset (was at {stats['reset_time'].strftime('%H:%M:%S')})")
                
                if stats['last_error']:
                    print(f"  Last error: {stats['last_error']}")
                
                total_limit += 5000 if stats['is_healthy'] else 0
            
            print(f"\nSummary:")
            print(f"  Healthy tokens: {self.get_healthy_token_count()}/{len(self.tokens)}")
            print(f"  Total remaining: {self.get_total_remaining_requests()} requests")
            print(f"  Max throughput: {total_limit} requests/hour")
            print("-" * 50)