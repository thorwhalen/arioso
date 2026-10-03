# arioso.services

### arioso.services *= ServiceCollection(ace_step, beatoven, elevenlabs, harmonai, jen, loudly, lyria2, lyria_rt, mubert, musicgen, riffusion, stable_audio, stable_audio_25, sunoapi, udio, yue)*

Lazy mapping of platform names to `ServiceHandle` objects.

Supports both `services["sunoapi"]` and `services.sunoapi`,
both returning the same `ServiceHandle`.
