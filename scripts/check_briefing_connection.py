"""Make one tiny Gemini request to separate provider errors from B workflow errors."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True,
                        help="Allow one real API request; uses API quota")
    parser.add_argument("--model", help="Default: the shared B/C SIA_AGENT_MODEL setting")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts/briefing/provider-check.json")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    import httpx
    from self_improving_ai.config import settings

    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        parser.error("Configure the local ignored .env API key first")
    model = args.model or settings.agent_model
    report = {"model": model, "tested_at_utc": datetime.now(timezone.utc).isoformat(),
              "test": "one_tiny_request_no_agent_no_tools", "attempts": 1}
    started = perf_counter()
    client = None
    try:
        client = genai.Client(http_options=types.HttpOptions(timeout=15000,
            retry_options=types.HttpRetryOptions(attempts=1)))
        response = client.models.generate_content(model=model, contents="Reply with exactly OK.",
            config=types.GenerateContentConfig(max_output_tokens=32))
        report.update(status="connected", http_status=200,
                      has_text=bool(response.text), usage=response.usage_metadata.model_dump(mode="json")
                      if response.usage_metadata else None)
    except APIError as exc:
        report.update(status="provider_error", http_status=exc.code,
                      hint={503: "Temporary provider capacity error; stop full workflow tests and retry later.",
                            429: "Check project quota and rate limits.",
                            404: "Model is unavailable for this account.",
                            400: "Provider rejected the request; inspect model/configuration compatibility.",
                            403: "Check API key permissions and account eligibility."}.get(
                                exc.code, "Provider request failed; inspect the error code."))
    except (TimeoutError, httpx.TimeoutException):
        report.update(status="timeout", hint="The minimal request did not finish within its timeout.")
    except Exception as exc:
        report.update(status="connection_error", error_type=type(exc).__name__)
    finally:
        if client is not None:
            client.close()
    report["elapsed_seconds"] = round(perf_counter() - started, 2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        args.output.chmod(0o600)
        json.dump(report, file, indent=2)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "connected" else 1


if __name__ == "__main__":
    raise SystemExit(main())
