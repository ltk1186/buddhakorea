#!/usr/bin/env python3
"""Test which Gemini models are available"""
from google.cloud import aiplatform
from google.cloud.aiplatform import generative_models

aiplatform.init(project="gen-lang-client-0324154376", location="us-central1")

# Test models including Gemini 2.0 Flash
models_to_try = [
    "gemini-2.0-flash-exp",       # Gemini 2.0 Flash (experimental) - Latest!
    "gemini-exp-1206",             # Experimental version
    "gemini-1.5-flash-002",        # Flash 1.5 stable v2
    "gemini-1.5-flash-001",        # Flash 1.5 stable v1
    "gemini-1.5-flash",            # Flash 1.5 (aliased to latest stable)
    "gemini-1.5-pro-002",          # Pro 1.5 stable v2
    "gemini-1.5-pro-001",          # Pro 1.5 stable v1
    "gemini-1.5-pro"               # Pro 1.5 (aliased to latest stable)
]

print("🔍 Testing Gemini models in us-central1...\n")
print(f"{'Model Name':<35} {'Status':<15} {'Details'}")
print("=" * 80)

working_models = []

for model_name in models_to_try:
    try:
        model = generative_models.GenerativeModel(model_name)
        response = model.generate_content("Hello")
        print(f"{model_name:<35} ✅ WORKS        Can generate content")
        working_models.append(model_name)
    except Exception as e:
        error_msg = str(e).split('\n')[0]
        if "404" in error_msg:
            status = "❌ NOT FOUND"
        elif "429" in error_msg:
            status = "⚠️  RATE LIMIT"
        elif "403" in error_msg:
            status = "🔒 NO ACCESS"
        else:
            status = "❌ ERROR"
        print(f"{model_name:<35} {status:<15} {error_msg[:40]}")

print("\n" + "=" * 80)
if working_models:
    print(f"\n✅ {len(working_models)} working model(s) found:")
    for m in working_models:
        print(f"   - {m}")
    print(f"\n💡 Recommended: Use '{working_models[0]}' for best performance")
else:
    print("\n❌ No working models found!")
    print("\n📝 Possible solutions:")
    print("   1. Enable Vertex AI API: gcloud services enable aiplatform.googleapis.com")
    print("   2. Request quota increase: https://cloud.google.com/vertex-ai/docs/quotas")
    print("   3. Try different region (e.g., 'us-west1', 'asia-northeast1')")
