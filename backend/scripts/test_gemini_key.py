"""Quick Gemini API key smoke test. Usage: python scripts/test_gemini_key.py"""

from __future__ import annotations

from google.genai import types

from app.core.config import settings
from app.services.gemini_client import gemini_keys, run_with_key_failover


def main() -> None:
    keys = gemini_keys()
    model = settings.GEMINI_MODEL
    print(f"Configured keys: {len(keys)}")
    for i, key in enumerate(keys, start=1):
        print(f"  {i}. suffix …{key[-4:]} (len={len(key)})")
    print(f"Model: {model}")

    print("\n--- Test 1: simple text (with key failover) ---")
    try:
        response = run_with_key_failover(
            lambda client: client.models.generate_content(
                model=model,
                contents="Reply with exactly: OK",
                config=types.GenerateContentConfig(max_output_tokens=20, temperature=0),
            )
        )
        print("PASS:", (response.text or "").strip())
    except Exception as exc:
        print("FAIL:", str(exc)[:900])

    print("\n--- Test 2: JSON output (with key failover) ---")
    try:
        response = run_with_key_failover(
            lambda client: client.models.generate_content(
                model=model,
                contents='Return JSON object with field status set to "ok"',
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=50,
                    temperature=0.1,
                ),
            )
        )
        print("PASS:", (response.text or "").strip()[:200])
    except Exception as exc:
        print("FAIL:", str(exc)[:900])


if __name__ == "__main__":
    main()
