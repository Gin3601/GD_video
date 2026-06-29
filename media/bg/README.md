# Background Video Library

Put vertical background videos here. The backend scans this folder recursively.

Recommended structure:

```text
media/bg/
  morning/
    healing/
      morning_healing_01.mp4
    motivational/
      morning_motivational_01.mp4
    calm/
      morning_calm_01.mp4
  cinematic/
    cinematic_01.mp4
  custom/
    your_custom_background.mp4
```

Supported formats: `.mp4`, `.mov`, `.mkv`, `.webm`.

Recommended video specs:

- Aspect ratio: 9:16 vertical
- Resolution: 720x1280 or 1080x1920
- Duration: 10-60 seconds
- No subtitles, no watermark, no important text near the bottom

Feishu usage:

- `背景来源` = `随机素材`
- `背景素材` can be empty, or set to a keyword such as `治愈`, `励志`, `calm`, `morning_motivational`.

Matching behavior:

- If `背景素材` is filled, the backend first searches matching folder/file names.
- Otherwise it tries `视频类型 + 风格`, then `风格`, then `视频类型`.
- If no match is found, it randomly picks one available video.
