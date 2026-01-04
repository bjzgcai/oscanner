"""Proxy configuration for API calls that need GFW bypass."""
import os

def get_image_api_proxies():
    """
    Get proxy configuration for image generation API calls.
    
    Returns dict for requests.post(proxies=...) or None if no proxy configured.
    
    Configuration priority:
    1. Environment variable IMAGE_API_PROXY (e.g., "socks5://localhost:7890")
    2. Return None (no proxy)
    
    Usage in server.py:
        proxies = get_image_api_proxies()
        response = requests.post(url, proxies=proxies, ...)  # None is valid
    """
    proxy_url = os.getenv('IMAGE_API_PROXY')
    
    if proxy_url:
        print(f"[Proxy Config] Using proxy for image API: {proxy_url}")
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    else:
        print("[Proxy Config] No proxy configured for image API")
        return None
