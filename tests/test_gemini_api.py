import google.generativeai as genai
import os

# Test with the key from .env
with open('.env') as f:
    for line in f:
        if line.startswith('VERTEX_AI_API_KEY='):
            api_key = line.split('=', 1)[1].strip()
            break

print(f"Testing with key: {api_key[:15]}...")

# This key format suggests it's for a different API
# Let's check if it works with the Gemini API endpoint directly
print("\nThe key format 'AQ.A...' suggests this is an OAuth token, not a Gemini API key.")
print("For Gemini API (generativelanguage.googleapis.com), you need an API key starting with 'AIzaSy...'")
print("\nYou can create one at: https://aistudio.google.com/app/apikey")
