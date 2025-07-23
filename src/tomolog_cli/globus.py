#!/usr/bin/env python3
"""
Globus file upload helper with refresh tokens
Minimal external module for tomolog integration
"""

import os
import json
import time
import webbrowser
from pathlib import Path
from datetime import datetime

import globus_sdk

# Configuration - update these for your setup
GLOBUS_LOCAL_ENDPOINT = "2f701431-55f6-11f0-ad13-0affcfc1d1e5"
GLOBUS_REMOTE_ENDPOINT = "144ef39b-65d9-4623-9d5d-7394499261a3" 
GLOBUS_REMOTE_BASE_PATH = "/test_tomolog/"
GLOBUS_BASE_URL = "https://g-df2e9.fd635.8443.data.globus.org/"
GLOBUS_CLIENT_ID = "95fdeba8-fac2-42bd-a357-e068d82ff78e"
GLOBUS_TOKEN_FILE = os.path.expanduser("~/.tomolog_globus_tokens.json")
GLOBUS_SCOPES = ["urn:globus:auth:scope:transfer.api.globus.org:all"]

class _GlobusAuth:
    """Internal Globus authentication handler"""
    
    def __init__(self):
        self.tokens = None
    
    def _load_tokens(self):
        if os.path.exists(GLOBUS_TOKEN_FILE):
            try:
                with open(GLOBUS_TOKEN_FILE, 'r') as f:
                    self.tokens = json.load(f)
                return True
            except:
                pass
        return False
    
    def _save_tokens(self, tokens):
        self.tokens = tokens
        os.makedirs(os.path.dirname(GLOBUS_TOKEN_FILE), exist_ok=True)
        with open(GLOBUS_TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=2)
        os.chmod(GLOBUS_TOKEN_FILE, 0o600)
    
    def _get_fresh_tokens(self):
        client = globus_sdk.NativeAppAuthClient(GLOBUS_CLIENT_ID)
        client.oauth2_start_flow(requested_scopes=GLOBUS_SCOPES, refresh_tokens=True)
        
        authorize_url = client.oauth2_get_authorize_url()
        print(f"\nGlobus Authentication Required")
        print(f"Please visit: {authorize_url}")
        
        try:
            webbrowser.open(authorize_url)
            print("Browser opened automatically.")
        except:
            print("Copy the URL above to your browser.")
        
        auth_code = input("\nPaste authorization code: ").strip()
        token_response = client.oauth2_exchange_code_for_tokens(auth_code)
        tokens = token_response.by_resource_server
        self._save_tokens(tokens)
        print("Globus tokens saved!")
        return tokens
    
    def _refresh_tokens(self):
        transfer_tokens = self.tokens.get('transfer.api.globus.org')
        if not transfer_tokens or 'refresh_token' not in transfer_tokens:
            return self._get_fresh_tokens()
        
        try:
            client = globus_sdk.NativeAppAuthClient(GLOBUS_CLIENT_ID)
            refresh_token = transfer_tokens['refresh_token']
            new_tokens = client.oauth2_refresh_token(refresh_token)
            new_transfer_tokens = new_tokens.by_resource_server['transfer.api.globus.org']
            self.tokens['transfer.api.globus.org'].update(new_transfer_tokens)
            self._save_tokens(self.tokens)
            return self.tokens
        except:
            return self._get_fresh_tokens()
    
    def get_client(self):
        if not self._load_tokens():
            self._get_fresh_tokens()
        
        transfer_tokens = self.tokens.get('transfer.api.globus.org', {})
        if 'refresh_token' not in transfer_tokens:
            self._get_fresh_tokens()
            transfer_tokens = self.tokens['transfer.api.globus.org']
        
        # Auto-refresh if needed
        if 'expires_at_seconds' in transfer_tokens:
            if time.time() > transfer_tokens['expires_at_seconds'] - 300:  # 5 min buffer
                self._refresh_tokens()
                transfer_tokens = self.tokens['transfer.api.globus.org']
        
        authorizer = globus_sdk.RefreshTokenAuthorizer(
            transfer_tokens['refresh_token'],
            globus_sdk.NativeAppAuthClient(GLOBUS_CLIENT_ID),
            access_token=transfer_tokens['access_token'],
            expires_at=transfer_tokens.get('expires_at_seconds')
        )
        
        return globus_sdk.TransferClient(authorizer=authorizer)

# Global instance
_auth = _GlobusAuth()

def upload_file(local_file, remote_subpath="slides/"):
    """
    Upload file to Globus and return HTTP URL
    
    Args:
        local_file: Path to local file
        remote_subpath: Remote subdirectory (default: "slides/")
    
    Returns:
        str: HTTP URL of uploaded file, or None if failed
    """
    if not os.path.exists(local_file):
        print(f"File not found: {local_file}")
        return None
    print(local_file)
    filename = Path(local_file).name
    remote_path = f"{GLOBUS_REMOTE_BASE_PATH}{remote_subpath}{filename}"
    
    try:
        tc = _auth.get_client()
        
        tdata = globus_sdk.TransferData(
            tc, GLOBUS_LOCAL_ENDPOINT, GLOBUS_REMOTE_ENDPOINT,
            label=f"Upload: {filename}", sync_level="mtime"
        )
        tdata.add_item(local_file, remote_path)
        
        result = tc.submit_transfer(tdata)
        http_url = f"{GLOBUS_BASE_URL}{remote_subpath}{filename}"
        
        print(f"Uploaded: {http_url}")
        return http_url
        
    except Exception as e:
        print(f"Upload failed: {e}")
        return None

def configure(local_endpoint=None, remote_endpoint=None, base_url=None):
    """Update configuration if needed"""
    global GLOBUS_LOCAL_ENDPOINT, GLOBUS_REMOTE_ENDPOINT, GLOBUS_BASE_URL
    if local_endpoint:
        GLOBUS_LOCAL_ENDPOINT = local_endpoint
    if remote_endpoint:
        GLOBUS_REMOTE_ENDPOINT = remote_endpoint  
    if base_url:
        GLOBUS_BASE_URL = base_url

