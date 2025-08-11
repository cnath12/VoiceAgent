#!/usr/bin/env python3
import os
import asyncio
from typing import Optional

from dotenv import load_dotenv

# Deepgram SDK
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

# Pipecat Cartesia TTS service
from pipecat.services.cartesia.tts import CartesiaTTSService


def mask(value: Optional[str]) -> str:
    if not value:
        return "<empty>"
    return value[:3] + "***" + value[-4:] if len(value) > 7 else "***"


def print_header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


async def check_deepgram(api_key: str) -> bool:
    print_header("Deepgram Key Check")
    try:
        client = DeepgramClient(api_key)
        live_options = LiveOptions(
            language="en-US",
            model="nova-2-medical",
            punctuate=True,
            interim_results=False,
            endpointing=300,
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
        )

        conn = client.listen.asyncwebsocket.v("1")
        error_holder: dict[str, Optional[str]] = {"err": None}

        async def on_error(self, error, **kwargs):
            error_holder["err"] = str(error)

        conn.on(LiveTranscriptionEvents.Error, on_error)

        await conn.start(live_options)
        await conn.finish()

        if error_holder["err"]:
            print(f"Deepgram reported error: {error_holder['err']}")
            return False

        print("Deepgram key OK: connection established and closed successfully")
        return True
    except Exception as e:
        print(f"Deepgram key check failed: {e}")
        return False


def check_cartesia(api_key: str) -> bool:
    print_header("Cartesia Key Check")
    try:
        _ = CartesiaTTSService(
            api_key=api_key,
            voice_id="professional-female-1",
            model="sonic-turbo",
            sample_rate=8000,
            encoding="pcm_s16le",
            container="raw",
        )
        print("Cartesia key appears valid: TTS service instantiated")
        print("Note: Full validation occurs during synthesis in the running pipeline.")
        return True
    except Exception as e:
        print(f"Cartesia key check failed: {e}")
        return False


async def main():
    load_dotenv()

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "")
    cartesia_key = os.getenv("CARTESIA_API_KEY", "")

    print_header("Environment Keys Overview")
    print(f"DEEPGRAM_API_KEY: {mask(deepgram_key)}")
    print(f"CARTESIA_API_KEY: {mask(cartesia_key)}")

    ok_dg = await check_deepgram(deepgram_key) if deepgram_key else False
    ok_ct = check_cartesia(cartesia_key) if cartesia_key else False

    print_header("Results")
    print(f"Deepgram: {'OK' if ok_dg else 'FAIL'}")
    print(f"Cartesia: {'OK' if ok_ct else 'FAIL'}")

    exit_code = 0 if (ok_dg and ok_ct) else 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())



