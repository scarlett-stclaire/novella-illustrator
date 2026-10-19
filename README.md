# Novella Illustrator

Paste or upload a story, break it into scenes with a local LLM (Ollama), then
generate an illustration per scene with a local image model (ComfyUI, with a
choice of engines - see below), editing prompts by hand before generating,
and giving feedback to regenerate a bad image (optionally with a different
engine).

## Stack

- `frontend/` - React + Vite
- `backend/` - FastAPI
- `ollama` - runs the scene-breakdown LLM (default `llama3.1:8b`)
- ComfyUI - runs image generation across multiple interchangeable engines
  (see "Image generation engines" below). Its source is cloned fresh by
  `scripts/setup.sh` into `comfyui/src/` (gitignored, disposable); only
  `comfyui/models/` (the weight files) and `comfyui/output/` persist.

Everything runs natively on macOS (no Docker) so it can use Apple Silicon's
GPU via Metal/MPS - Docker Desktop on macOS cannot pass the GPU through to
containers, which made FLUX impractically slow and memory-constrained in a
container.

### Moving to another machine

Only `comfyui/models/*.safetensors` is worth transporting (rsync/copy/drive)
- they're plain weight files, identical on any OS or architecture. Everything
else (venvs, the cloned ComfyUI source, node_modules) is disposable: on the
new machine, copy the repo (or git clone) plus that `models/` folder, then
just re-run `scripts/setup.sh`.

Note: on this machine `unet/flux1-schnell.safetensors` and `vae/ae.safetensors`
are symlinks into the local Hugging Face cache (`~/.cache/huggingface/...`),
done to avoid duplicating ~24GB on a disk with limited free space - see the
comment in `scripts/setup.sh`. Use `rsync -L` / `cp -L` (dereference
symlinks) when copying `models/` elsewhere, or replace the symlinks with real
files (`hf download black-forest-labs/FLUX.1-schnell flux1-schnell.safetensors
ae.safetensors --local-dir comfyui/models`-ish) if disk space allows.

## Setup

1. `./scripts/setup.sh` - installs/checks `ollama` and `node` via Homebrew,
   creates Python venvs for the backend and ComfyUI, runs `npm install`, and
   clones ComfyUI source into `comfyui/src/`. Also clones the
   `ComfyUI-Impact-Pack` / `ComfyUI-Impact-Subpack` custom nodes (needed for
   the SDXL + ADetailer engine's face/hand auto-fix). Safe to re-run anytime.
2. Download model weights for whichever engine(s) you want (not included,
   none are required to use the app - see "Image generation engines" below
   for exact files/commands per engine). You only need one engine to start.
3. `./scripts/start.sh` - starts ollama, ComfyUI, the backend and the
   frontend in the background (logs in `logs/`, pids in `.pids/`).
4. Open http://localhost:3000
5. `./scripts/stop.sh` when done.

Without any image model weights, scene breakdown (Ollama) still works; only
the "Generate image" step will fail until at least one engine's weights are
in place. The app only offers engines whose weights are actually present
(checked live against what ComfyUI has loaded).

## Desktop app (Tauri)

`src-tauri/` wraps the frontend and native dev setup in a real macOS window,
so `ollama`/ComfyUI/the backend start and stop with the app instead of
needing `scripts/start.sh`/`stop.sh` run from a terminal. Run `scripts/setup.sh`
(and download at least one engine's weights) first, same as above - the
desktop app launches those same native processes, it doesn't bundle them.

- `npx @tauri-apps/cli@latest dev` - run the desktop app against live-reloading
  frontend/backend code, same convenience as `scripts/start.sh` plus a real
  window.
- `npx @tauri-apps/cli@latest build` - produce an unsigned release `.app` at
  `src-tauri/target/release/bundle/macos/novella-illustrator.app`.

**Unsigned by design**: this project deliberately stays outside Apple's paid
developer program - no Developer ID, no notarized `.dmg`. Tagged pushes
(`git tag v0.1.0 && git push --tags`) trigger `.github/workflows/release.yml`,
which builds the app and attaches a plain `.tar.gz` (not a `.dmg`) to a
GitHub Release. Extracting via `tar -xzf` (not Finder) avoids the
`com.apple.quarantine` flag that triggers Gatekeeper's "unidentified
developer" block, so this works without a signing certificate - at the cost
of the usual drag-to-Applications double-click experience a signed `.dmg`
would give.

## Image generation engines

Pick one engine to start with, or set up all three and switch between them
per-scene in the UI (handy when one engine mangles an image - try "Regenerate
with fix" on a different engine). All commands assume the `hf` CLI
(`pip install -U huggingface_hub[cli]`) and are run from the repo root.

### FLUX.1-schnell (fast, 4 steps, no negative prompt)

```
hf download black-forest-labs/FLUX.1-schnell flux1-schnell.safetensors ae.safetensors \
  --local-dir comfyui/models  # then move unet/vae files into comfyui/models/unet/ and /vae/
hf download comfyanonymous/flux_text_encoders clip_l.safetensors t5xxl_fp8_e4m3fn.safetensors \
  --local-dir comfyui/models/clip
```
Requires a free huggingface.co account + accepting FLUX.1-schnell's license.
`flux1-schnell.safetensors` -> `comfyui/models/unet/`, `ae.safetensors` ->
`comfyui/models/vae/`. ~24GB. Fastest engine (~2.5-4 min/image on Apple
Silicon MPS), but prone to anatomy/hand contortion with no negative-prompt
input to correct it.

### SDXL + ADetailer (best anatomy fixing, ~3 min/image)

```
hf download stabilityai/stable-diffusion-xl-base-1.0 sd_xl_base_1.0.safetensors \
  --local-dir comfyui/models/checkpoints
hf download Bingsu/adetailer face_yolov8m.pt hand_yolov8n.pt \
  --local-dir comfyui/models/ultralytics/bbox
```
~7GB total. After the main image, ComfyUI's Impact Pack auto-detects faces
and hands and runs a targeted inpaint-fix pass on each - the engine built
specifically to address contorted limbs/hands.

### Qwen-Image-2512 (sharpest detail, best text rendering, ~6-9 min/image)

```
hf download Comfy-Org/Qwen-Image_ComfyUI \
  split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors \
  split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors \
  split_files/vae/qwen_image_vae.safetensors \
  --local-dir comfyui/models  # then move each into diffusion_models/, text_encoders/, vae/
hf download lightx2v/Qwen-Image-2512-Lightning Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors \
  --local-dir comfyui/models/loras
```
~32GB. Apache 2.0, no login needed. The Lightning LoRA is required for
practical speed - without it this engine runs 50 steps instead of 4 and
takes well over an hour per image on MPS.

After downloading any engine's weights, restart ComfyUI
(`./scripts/stop.sh && ./scripts/start.sh`) so it picks up the new files.

## API

- `POST /api/novellas` `{title, text, target_scene_count?}` - create a novella
- `POST /api/novellas/{id}/breakdown` - LLM breaks text into scenes
  (background; poll `GET /api/novellas/{id}` for progress)
- `PATCH /api/novellas/{id}/scenes/{scene_id}` `{image_prompt}` - edit a
  scene's prompt by hand
- `POST /api/novellas/{id}/scenes` `{summary, image_prompt, after_scene_id?}` -
  insert a hand-written scene
- `DELETE /api/novellas/{id}/scenes/{scene_id}` - remove a scene
- `POST /api/novellas/{id}/scenes/{scene_id}/generate?engine_id=` - generate
  that scene's illustration (background; `engine_id` optional, defaults to
  `DEFAULT_IMAGE_ENGINE`)
- `POST /api/novellas/{id}/scenes/{scene_id}/regenerate`
  `{feedback, engine_id?}` - regenerate with correction notes (e.g. "hands
  look contorted"), optionally on a different engine
- `GET /api/engines` - lists registered engines and whether each is currently
  available (weights present)
- `GET /api/health` - reports whether Ollama and ComfyUI are reachable

## Style

Every generated prompt has `ILLUSTRATION_STYLE_HINT` (see `.env.example`)
appended, so all scenes share a consistent look without needing true
image-conditioned style transfer.
