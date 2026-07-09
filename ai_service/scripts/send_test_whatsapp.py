"""
send_test_whatsapp.py — one-shot check that Twilio WhatsApp actually delivers.

Run this AFTER setting TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN /
TWILIO_WHATSAPP_FROM in ai_service/.env. It sends one real message through the
exact same code path Agent 6's nudge batch uses (utils.whatsapp_sender), so a
success here means the whole nudge pipeline can deliver.

Usage:
    python -m ai_service.scripts.send_test_whatsapp +91XXXXXXXXXX

For the Twilio SANDBOX (instant, no Business approval needed), the recipient
number must FIRST join the sandbox by sending the "join <two-word-code>"
message (shown in the Twilio console) to the sandbox WhatsApp number.
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.utils.whatsapp_sender import is_live, send_whatsapp  # noqa: E402


async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m ai_service.scripts.send_test_whatsapp +91XXXXXXXXXX")
        sys.exit(1)
    to = sys.argv[1].strip()

    if not is_live():
        print("Twilio is NOT configured — set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / "
              "TWILIO_WHATSAPP_FROM in ai_service/.env first. (send_whatsapp would just dry-run.)")
        sys.exit(2)

    body = "✅ Yojna Setu test: agar aapko ye message mila, toh WhatsApp nudges kaam kar rahe hain!"
    print(f"Sending real WhatsApp to {to[:3]}****{to[-2:]} ...")
    result = await send_whatsapp(to, body)
    print("result:", result)
    if result.get("delivered"):
        print(f"SUCCESS — message queued/sent (sid={result.get('sid')}). Check the phone.")
    else:
        print(f"NOT delivered: status={result.get('status')} error={result.get('error')}")
        print("Common sandbox cause: the recipient hasn't sent the 'join <code>' message yet.")


if __name__ == "__main__":
    asyncio.run(main())
