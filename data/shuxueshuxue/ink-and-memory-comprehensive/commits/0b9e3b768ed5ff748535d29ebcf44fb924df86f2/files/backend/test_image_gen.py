#!/usr/bin/env python3
"""Test Gemini image generation via dou.chat endpoint"""

import requests
import json
import base64
from pathlib import Path

API_KEY = "sk-yz0JLc7sGbCHnwam70Bc9e29Dc684bAe904102C95dF32fB1"
ENDPOINT = "https://api.dou.chat/v1"
MODEL = "google/gemini-2.5-flash-image-preview"

def test_image_generation():
    """Test if image generation works with the given model"""

    print(f"\n{'='*60}")
    print(f"🎨 Testing Image Generation")
    print(f"   Endpoint: {ENDPOINT}")
    print(f"   Model: {MODEL}")
    print(f"{'='*60}\n")

    # Try a simple prompt
    prompt = "A serene morning scene with a cup of coffee on a wooden table, sunlight streaming through a window, peaceful and contemplative mood"

    print(f"Prompt: {prompt}\n")

    # Make request
    url = f"{ENDPOINT}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000
    }

    print("Sending request...")
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("\n✅ Success!")
            print(json.dumps(data, indent=2))

            # Check if there's image data
            if 'choices' in data and len(data['choices']) > 0:
                message = data['choices'][0].get('message', {})
                images = message.get('images', [])

                if images:
                    print(f"\n🖼️  Found {len(images)} image(s)!")

                    # Extract first image
                    image_data = images[0].get('image_url', {}).get('url', '')

                    if image_data.startswith('data:image/png;base64,'):
                        # Extract base64 data
                        base64_data = image_data.split(',', 1)[1]

                        # Decode and save
                        image_bytes = base64.b64decode(base64_data)
                        output_path = Path("/tmp/test_gemini_image.png")
                        output_path.write_bytes(image_bytes)

                        print(f"✅ Image saved to: {output_path}")
                        print(f"   Size: {len(image_bytes)} bytes")
                        print(f"\n💡 Open with: open {output_path}")
                    else:
                        print(f"⚠️  Unexpected image format: {image_data[:100]}...")
                else:
                    print("\n❌ No images found in response")

        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    test_image_generation()
