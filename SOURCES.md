# Source review — 10 November 2026

All eleven supplied LinkedIn short URLs were attempted; none could be opened through the research tool. The following official projects were identified independently by name. The destinations of the short URLs are **not confirmed**. This is a repository/documentation review, not a full upstream source audit.

| Supplied link | Official project reviewed | Findings |
|---|---|---|
| https://lnkd.in/eDQwredw | [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | BSD-3-Clause. Detects boundaries; FFmpeg provides splitting. |
| https://lnkd.in/eWwerpGT | [Auto-Editor](https://github.com/WyattBlue/auto-editor) | Unlicense. Loudness-based editing and configurable margins; current repository uses Nim. Follow its installation instructions rather than assuming old Python packages match. |
| https://lnkd.in/eGKSvRi6 | [vid.stab](https://github.com/georgmartius/vid.stab) | Current source LGPL-2.1-or-later; releases through 1.1.2 were GPL. FFmpeg build configuration still matters. Two-pass stabilization. |
| https://lnkd.in/eAzCWk_k | [color-matcher](https://github.com/hahnec/color-matcher) | GPLv3 license text. Image reference transfer; adapter must process frames and restore audio. |
| https://lnkd.in/e38vb_ey | [rembg](https://github.com/danielgatis/rembg) | MIT code. Image foreground extraction. This project selects local u2net, not rembg's optional hosted services. Model terms are separate. |
| https://lnkd.in/ecZFx8hg | [RIFE](https://github.com/hzwer/ECCV2022-RIFE) | MIT code. Weights required. Explicit FPS controls playback duration; frame interpolation alone does not necessarily slow playback. |
| https://lnkd.in/e5TdFW8T | [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) | BSD-3-Clause code. Official README links NCNN Vulkan binaries for several GPU vendors. 4× enhancement cannot guarantee recovery of real detail. |
| https://lnkd.in/e64fG-4A | [Demucs](https://github.com/facebookresearch/demucs) | MIT. Original repository says it is no longer maintained and points to [author's fork](https://github.com/adefossez/demucs), accepting important bug fixes only. |
| https://lnkd.in/e6ZqdpkW | [librosa](https://github.com/librosa/librosa) | ISC. Audio analysis supplies beat timings; the application must implement cut scheduling. |
| https://lnkd.in/embGfA4h | [HyperFrames](https://github.com/heygen-com/hyperframes) | Apache-2.0 framework. Renders HTML/media/seekable animations. Separate commercial Studio features are not required by this project. |
| https://lnkd.in/evx5Xivu | [FFmpeg](https://github.com/FFmpeg/FFmpeg) | Primarily LGPL; optional GPL components change build terms. Encoding/decoding availability depends on the installed build. |

Useful implementation references:

- [ColorMatcher transfer/normalization API](https://github.com/hahnec/color-matcher#api-usage)
- [RIFE video inference source](https://github.com/hzwer/ECCV2022-RIFE/blob/main/inference_video.py)
- [HyperFrames introduction and render command](https://hyperframes.app/docs/1-startup/1-introduction)
- [vid.stab current license and historical note](https://github.com/georgmartius/vid.stab/blob/master/LICENSE)
- [FFmpeg license details](https://github.com/FFmpeg/FFmpeg/blob/master/LICENSE.md)

The promotional claim about “Claude Opus 5.5” is not a dependency or a verified benchmark. This workflow requires no Claude subscription. An optional language-model layer could later translate editing requests into validated workflow JSON.
