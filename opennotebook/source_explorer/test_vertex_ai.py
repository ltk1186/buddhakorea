#!/usr/bin/env python3
"""Quick test to see if Vertex AI Gemini works with updated model"""
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

# Initialize
PROJECT_ID = "gen-lang-client-0324154376"
LOCATION = "us-central1"
vertexai.init(project=PROJECT_ID, location=LOCATION)

# Test models
models_to_test = [
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]

print("🧪 Testing Vertex AI Gemini models...\n")
print(f"{'Model':<30} {'Status':<15} {'Response Preview'}")
print("=" * 80)

working_model = None

for model_name in models_to_test:
    try:
        model = GenerativeModel(model_name)
        response = model.generate_content(
            "Say 'Hello' in Korean",
            generation_config=GenerationConfig(
                temperature=0.3,
                max_output_tokens=50
            )
        )
        preview = response.text[:30].replace('\n', ' ')
        print(f"{model_name:<30} ✅ WORKS         {preview}")
        working_model = model_name
        break  # Found working model, stop testing
    except Exception as e:
        error = str(e)[:50].replace('\n', ' ')
        status = "❌ FAILED"
        if "429" in error:
            status = "⚠️  QUOTA"
        elif "404" in error:
            status = "❌ NOT FOUND"
        print(f"{model_name:<30} {status:<15} {error}")

print("\n" + "=" * 80)
if working_model:
    print(f"✅ SUCCESS! Use: {working_model}")
    print(f"💰 This uses your GCP credits (no extra cost)")
    print(f"🚀 Ready to process 2,233 remaining Buddhist texts")
else:
    print("❌ No working models found")
    print("\n📝 Options:")
    print("   1. Request quota increase: https://console.cloud.google.com/iam-admin/quotas")
    print("   2. Use Google AI Studio API (separate from GCP, has free tier)")
