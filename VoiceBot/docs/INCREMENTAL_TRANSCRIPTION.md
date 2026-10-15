# Incremental microphone transcription

Voice capture now sends cumulative WebM prefixes to the existing Whisper medium/CUDA model while the learner speaks. This is incremental snapshot transcription, not a natively streaming Whisper decoder. Cumulative prefixes retain the container header; individual MediaRecorder chunks are not independently decoded.

- At most one partial request is in flight for a capture; busy requests are skipped rather than queued.
- Snapshots run approximately every 1.5 seconds during speech, with a final opportunity during the existing silence-detection interval.
- Partial text is provisional and never creates a conversation turn.
- At recording end, a confident nonempty snapshot is reused only if it covers at least 150 ms beyond the last detected speech. Otherwise the complete recording is transcribed through the previous path.
- Capture cancellation/unmount aborts requests and prevents late provisional text or canceled input from being submitted.
- The endpoint accepts `partial=true` and reports partial processing separately in the bounded in-memory monitor. No extra audio files or transcript records are saved by this feature.

Expected benefit: recognition work overlaps speaking and endpointing. Actual benefit depends on recording length, decoder support for unfinished WebM prefixes, GPU load and snapshot timing. Long recordings repeat work and require real-device load/accuracy validation; this does not solve ChatTTS's generation delay. Existing Whisper model, silence threshold and learner UI layout are unchanged.

Tests: `node --test src/incrementalTranscriber.test.mjs` in frontend, Python API/full regression suite, and frontend production build. Physical microphone latency and accuracy still require a user trial.
