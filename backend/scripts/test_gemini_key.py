"""Quick Gemini API key smoke test. Usage: python scripts/test_gemini_key.py"""

from __future__ import annotations

import httpx
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.http_client import create_sync_client


def main() -> None:
    key = settings.GEMINI_API_KEY
    model = settings.GEMINI_MODEL
    print(f"Key prefix: {key[:10]}...")
    print(f"Model: {model}")

    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(httpx_client=create_sync_client()),
    )

    print("\n--- Test 1: simple text ---")
    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: OK",
            config=types.GenerateContentConfig(max_output_tokens=20, temperature=0),
        )
        print("PASS:", (response.text or "").strip())
    except Exception as exc:
        print("FAIL:", str(exc)[:900])

    print("\n--- Test 2: JSON output ---")
    try:
        response = client.models.generate_content(
            model=model,
            contents='Return JSON object with field status set to "ok"',
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=50,
                temperature=0.1,
            ),
        )
        print("PASS:", (response.text or "").strip()[:200])
    except Exception as exc:
        print("FAIL:", str(exc)[:900])


if __name__ == "__main__":
    main()
