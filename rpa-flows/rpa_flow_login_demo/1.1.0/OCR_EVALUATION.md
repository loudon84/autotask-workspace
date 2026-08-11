# Login Demo OCR Evaluation

## Environment

```text
Windows 10 x64 / QEMU Virtual CPU
Python 3.11.15
ddddocr 1.6.1
onnxruntime 1.16.3
numpy 1.26.4
opencv-python 4.10.0.84
```

`onnxruntime` 1.23.2 and 1.27.0 could not load on this Windows runtime. The version combination above passed `pip check` and loaded successfully.

## Fixed Image Benchmark

The benchmark read image bytes only. The image filename was used to select the expected answer for scoring, never as OCR input.

| Image | Expected | OCR | Match |
| --- | --- | --- | --- |
| code01 | mp3s | mp3s | yes |
| code02 | 0ada | oada | no |
| code03 | sez0 | sezo | no |
| code04 | ggmh | ggn4 | no |
| code05 | rpyt | rpyt | yes |
| code06 | y5na | y5na | yes |
| code07 | elhx | elhx | yes |
| code08 | el0m | elom | no |
| code09 | aqh9 | aqh9 | yes |
| code10 | gqcy | gqcy | yes |

Result: `6/10`, or `60%` exact-match accuracy.

Model initialization took about 104 ms. Per-image inference took about 6-43 ms. Grayscale, autocontrast, sharpening, thresholding, and 2x-4x scaling did not improve exact-match accuracy. Restricting the classifier to lowercase alphanumeric characters reduced accuracy to 40%.

## Browser Flow Benchmark

The first OCR Flow implementation was executed through `flow.py:run(ctx)` in 20 isolated Playwright BrowserContexts:

```text
Successful login: 11/20 (55%)
Succeeded on first OCR attempt: 8
Succeeded after one captcha refresh: 3
WAITING_HUMAN: 9
```

One-attempt success usually took about 1.3 seconds. A retry or rejected second captcha usually took about 4.5-5.3 seconds.

After this run, the Flow was adjusted to read the image's natural pixels through an in-page Canvas instead of relying only on the CSS-scaled element screenshot. Structurally invalid OCR output now consumes the one allowed refresh before moving to `WAITING_HUMAN`.

The final Canvas-based implementation was then executed through the same `flow.py:run(ctx)` entrypoint in another 20 isolated BrowserContexts:

```text
Successful login: 17/20 (85%)
Succeeded on first OCR attempt: 11
Succeeded after one captcha refresh: 6
WAITING_HUMAN: 3
Average Flow duration: 2882.9 ms
```

One-attempt successes took about 1.2-1.4 seconds. Second-attempt successes took about 5.1-5.2 seconds, while twice-rejected runs moved to `WAITING_HUMAN` in about 4.3-4.4 seconds. All three unsuccessful runs reported `CAPTCHA_OCR_FAILED`; there were no crashes or uncontrolled retries.

## Conclusion

The OCR path is fast enough but is not reliable enough for unattended login. Model confidence also remained high on several wrong predictions, so a confidence threshold cannot safely distinguish every failure.

Flow version 1.1.0 therefore:

1. Uses image bytes instead of the static filename map.
2. Allows at most one captcha refresh and OCR retry.
3. Moves to `WAITING_HUMAN` when OCR is unavailable, structurally invalid, or rejected twice.
4. Does not log the recognized captcha text.

This version is an OCR feasibility experiment. Natural-pixel Canvas capture raised the measured end-to-end login success rate from 55% to 85%, but the final sample still required human handling in 3 of 20 runs. That is not reliable enough for unattended production login. It must retain human fallback until a larger portal-specific dataset, portal-specific model work, and an accuracy target agreed with the business owner demonstrate acceptable reliability.
