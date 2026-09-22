# arioso.platforms

Platform packages for arioso.

Each subdirectory is a platform plugin containing at minimum a
`config.py` with a `PLATFORM_CONFIG` dict. Platforms are
auto-discovered by [`arioso.registry.discover_platforms()`](arioso.registry.md#arioso.registry.discover_platforms).

### Modules

| [`beatoven`](arioso.platforms.beatoven.md#module-arioso.platforms.beatoven)         | Beatoven.ai platform for arioso.                |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------|
| [`elevenlabs`](arioso.platforms.elevenlabs.md#module-arioso.platforms.elevenlabs)     | ElevenLabs Music platform for arioso.           |
| [`harmonai`](arioso.platforms.harmonai.md#module-arioso.platforms.harmonai)         | Harmonai (Dance Diffusion) platform for arioso. |
| [`jen`](arioso.platforms.jen.md#module-arioso.platforms.jen)                   | Jen platform for arioso.                        |
| [`loudly`](arioso.platforms.loudly.md#module-arioso.platforms.loudly)             | Loudly platform for arioso.                     |
| [`lyria2`](arioso.platforms.lyria2.md#module-arioso.platforms.lyria2)             | Google Lyria 2 platform for arioso.             |
| [`lyria_rt`](arioso.platforms.lyria_rt.md#module-arioso.platforms.lyria_rt)         | Google Lyria RealTime platform for arioso.      |
| [`mubert`](arioso.platforms.mubert.md#module-arioso.platforms.mubert)             | Mubert platform for arioso.                     |
| [`musicgen`](arioso.platforms.musicgen.md#module-arioso.platforms.musicgen)         | MusicGen platform for arioso.                   |
| [`riffusion`](arioso.platforms.riffusion.md#module-arioso.platforms.riffusion)       | Riffusion platform for arioso.                  |
| [`stable_audio`](arioso.platforms.stable_audio.md#module-arioso.platforms.stable_audio) | Stable Audio Open platform for arioso.          |
| [`sunoapi`](arioso.platforms.sunoapi.md#module-arioso.platforms.sunoapi)           | Suno platform (via sunoapi.org) for arioso.     |
| [`udio`](arioso.platforms.udio.md#module-arioso.platforms.udio)                 | Udio platform (via UdioWrapper) for arioso.     |
| [`yue`](arioso.platforms.yue.md#module-arioso.platforms.yue)                   | YuE platform for arioso.                        |
