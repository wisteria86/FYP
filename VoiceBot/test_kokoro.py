import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
import numpy as np
from modules.tts_kokoro import KokoroTTS
from io_interfaces.speaker_player import SpeakerPlayer
import wave

def main():
    print("Initializing Kokoro TTS...")
    tts = KokoroTTS(lang='j', voice='jf_alpha')
    print(f"Kokoro output sample rate: {tts.output_sample_rate}Hz")
    
    print("Initializing Speaker Player...")
    try:
        speaker = SpeakerPlayer(sample_rate=tts.output_sample_rate)
    except Exception as e:
        print(f"Failed to initialize SpeakerPlayer: {e}")
        return

    text = "こんにちは！私の声が聞こえますか？"
    print(f"Synthesizing text: {text}")
    
    audio_chunks = []
    try:
        for chunk in tts.synthesize(text, speed=1.0):
            print(f"Yielded chunk of {len(chunk)} bytes")
            audio_chunks.append(chunk)
            speaker.play_audio(chunk)
    except Exception as e:
        print(f"Error during synthesize or playback: {e}")
        return

    full_audio = b"".join(audio_chunks)
    print(f"Total audio generated: {len(full_audio)} bytes")
    
    # Save to file to verify audio format
    with wave.open("test_output.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit PCM expected by SpeakerPlayer??
        wf.setframerate(tts.output_sample_rate)
        
        # Kokoro yields float32, let's see what SpeakerPlayer expects!
        wf.writeframes(full_audio)
    print("Saved to test_output.wav")
    print("Test complete.")

if __name__ == "__main__":
    main()
