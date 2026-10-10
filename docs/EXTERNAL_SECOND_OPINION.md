# External vision second opinion

WildfireWatch keeps the locally trained YOLO detector as its primary screen. An operator may request one optional OpenAI vision review per report from the evidence panel. For a photo, the request contains that image. For a video, it contains at most two sampled frames: the highest-scoring local frame and a temporally distant sample. The API does not send the report's location, notes, or identity fields to the vision model.

The external review is a separate opinion, not a replacement or an average. Both models can be wrong, and their scores are uncalibrated. Agreement is not confirmation; disagreement directs attention back to the source media and another observation. The feature cannot issue alerts, notify agencies, or recommend evacuation.

To enable it with the full-stack demo runner, add `OPENAI_API_KEY=...` to the ignored repository-root `.env` file, then restart `./scripts/share_demo.sh`. The runner reads simple app configuration entries from `.env` without evaluating it as shell code; variables already exported in the shell take precedence. `OPENAI_VISION_MODEL` is optional and defaults to `gpt-4.1-mini`. Keep the key server-side; never place it in frontend code, send it in chat, or commit a public repository. `/api/status` reports only whether the key is configured and which model name is selected. No external vision call happens during upload or monitoring; an operator must press **Request external second opinion**. This API use may incur provider charges. The request is capped to one review per report to avoid repeated calls.

If no API key is available, the option remains disabled by design. A ChatGPT subscription does not provide an API key. Local YOLO analysis remains available without this optional provider.

For Railway, configure the same variables in the service's environment and redeploy before the feature can be enabled on the hosted dashboard. Keep user consent and applicable privacy rules in mind before transmitting community-submitted imagery to an external provider.
