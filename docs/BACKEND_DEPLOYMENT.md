# Hosting the trained model and dashboard

The Dockerfile serves the existing React dashboard, FastAPI/WebSockets, and the trained smoke detector together from one origin. The separate Sites deployment remains unchanged. Cloudflare Workers cannot run this PyTorch backend.

A former Railway sandbox served the frontend, FastAPI, and trained YOLO model,
but Railway sandboxes are temporary and the current Railway project has no
persistent service. Do not share the expired preview URL as a working deployment.

## Temporary public full-stack demo (no paid hosting)

The lowest-cost full-stack demo runs on the trusted Mac and publishes it through
a Cloudflare Quick Tunnel. Install `cloudflared` using the [official macOS
instructions](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/),
then run from the repository root:

```sh
./scripts/share_demo.sh
```

The script rebuilds the React dashboard, starts FastAPI and the trusted local
YOLO checkpoint on loopback, then opens a temporary HTTPS URL. API requests and
WebSockets use the same origin. It turns on the existing operator sign-in with a
random password and prints that password once; send the password separately to
demo viewers. Stop with Ctrl-C. Both the Mac and process must remain online, and
the URL changes after restart. This is suitable for a live pitch/demo, not
permanent public hosting. Quick Tunnels are temporary development links; see
[Cloudflare's documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).

The persistent Railway project currently contains no service. Publishing there
requires a GitHub-backed service and may consume credits; do not upgrade or add
paid hosting without reviewing the current plan and spend limits. The static
Sites page is separate and does not run Python inference.

Optional external integrations still need configuration: NASA FIRMS requires a
free map key or imported CSV, and OpenAI second-opinion review requires an API
key. Local YOLO inference, report upload/review, camera monitoring, API routes,
and WebSocket updates do not require those optional credentials. For the
temporary demo, add `OPENAI_API_KEY=...` to the ignored root `.env` file and
restart the runner to enable the external review button. It makes a provider
API request only when an operator clicks the button and may incur provider
charges. Do not put the key in the browser or commit `.env`.

## Container

Run from the complete source bundle (including `models/smoke-detector.pt`):

```sh
docker build -t wildfirewatch .
docker run --rm -p 7860:7860 -e PUBLIC_ORIGIN=http://localhost:7860 wildfirewatch
```

Open `http://localhost:7860`. Use the photo-reporting view to upload a frame and observer coordinates, or load the staged demonstration. CPU inference uses the bundled weights; no OpenAI key is required. Health/status is `/api/status`, and live events use `/ws`.

On a host, set `PORT` to its assigned port and `PUBLIC_ORIGIN` to the exact HTTPS service origin. Render supplies `RENDER_EXTERNAL_URL`, which the entry point adds to the allowed origins automatically. Keep a single worker and one service replica: the current incident/monitor state is in memory. A restart clears that state.

The trained checkpoint is excluded from Git. Deploy the complete bundle as a container image, or explicitly include the 5.2 MB trusted checkpoint in the hosting source upload. Never upload the raw datasets or `.env` files. CPU-only Torch is installed to avoid shipping unnecessary GPU runtimes.

## Access and validation

For Hugging Face, authenticate on the local computer with
`/Users/aarushkampani/Desktop/HTHS/wildfirewatch/.venv/bin/hf auth login`.
Use a token with write permission from `https://huggingface.co/settings/tokens`;
never put it in source, a Docker build argument, the Space variables, or chat.
The deployment client uses it locally to upload source, not inside the app.
Current Hugging Face rules require a compute-eligible paid plan to create a new
Docker Space on CPU Basic. No plan purchase or hardware upgrade is authorized.

Run `.venv/bin/python deploy/prepare_huggingface.py` to stage only the required
files with a Docker Space README. Create the Space as **private**, SDK **Docker**,
hardware **CPU Basic**, and upload that staged folder. Set `PUBLIC_ORIGIN` to the
Space's exact HTTPS `.hf.space` origin. Never expose the separate Python server
publicly just to bypass private access. Source/model upload must be followed by
runtime and browser checks before calling the deployment verified.

This is a shared, single-operator research prototype. Put the service behind the hosting provider's private access control before exposing it to visitors. The existing private Sites sign-in does not authenticate a separate Python service. Do not assume the origin check is user authentication.

After the host finishes building, check that `/api/status` returns `local_vision_available: true`, load the map, upload a frame, run local detection, and verify WebSocket stage updates and operator review. A live deployment is not verified until those checks pass. The local model remains experimental; see `COMBINED_DETECTOR.md` for test results and limitations.

If the existing Sites URL must remain the primary dashboard address, it additionally needs a configured HTTPS API base URL, CORS, and matching authentication to the external backend. Serving the dashboard and backend together avoids that cross-origin wiring.
