# Live TTS comparison — 10 October 2026

Same input: “Hello, it is lovely to meet you. How are you today?”
Three sequential HTTP requests per engine, existing running app, no STT or LLM included. First audio means received audio data, not audible browser playback. This is a small live sample, not a controlled-load capacity benchmark.

| Engine | Trial 1 | Trial 2 | Trial 3 | Median first audio / total |
| --- | ---: | ---: | ---: | ---: |
| Kokoro CPU | 7.197 s | 7.181 s | 7.166 s | 7.181 s |
| ChatTTS CUDA | 15.106 s | 16.600 s | 16.022 s | 16.022 s |

Both produced one chunk: first audio and total generation were effectively identical. ChatTTS currently explicitly decodes a continuous utterance with stream=False to avoid playback underruns. All its inspected model modules were on cuda:0 (RTX 5060), GPT bfloat16. ChatTTS activation/warmup was 12.004 seconds, excluded from response measurements.

Earlier Kokoro smoke test was 3.23 seconds. The new results demonstrate variability; they do not establish the reason for that slowdown. Further stage-level profiling under controlled load is required. Original Kokoro/af_heart selection was restored after testing.

Reproduce with `.venv\Scripts\python.exe scripts\benchmark_tts_engines.py`. This temporarily changes the global engine; avoid using an active call during the benchmark.
