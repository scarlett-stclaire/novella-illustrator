import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"

DEFAULT_NEGATIVE_PROMPT = os.environ.get(
    "DEFAULT_NEGATIVE_PROMPT",
    # Anatomy/quality basics, plus the gothic style sheet's own "Never" list
    # (specs/Novella Comic Generator Design.zip's Art Direction sheet) -
    # glossy/airbrushed skin, camera artifacts, and off-palette gradients
    # are exactly what would make a panel look generated instead of printed.
    "bad anatomy, extra fingers, missing fingers, malformed hands, fused fingers, "
    "extra limbs, mutated hands, blurry, low quality, watermark, deformed, "
    "glossy airbrushed skin, lens flare, bokeh, god rays, purple and teal gradient, "
    "oversaturated colors, photorealistic, 3d render, floating text, embedded typography",
)

FLUX_UNET_NAME = os.environ.get("FLUX_UNET_NAME", "flux1-schnell.safetensors")
FLUX_CLIP_NAME1 = os.environ.get("FLUX_CLIP_NAME1", "clip_l.safetensors")
FLUX_CLIP_NAME2 = os.environ.get("FLUX_CLIP_NAME2", "t5xxl_fp8_e4m3fn.safetensors")
FLUX_VAE_NAME = os.environ.get("FLUX_VAE_NAME", "ae.safetensors")


@dataclass
class Engine:
    id: str
    label: str
    workflow_file: str
    output_node: str
    prompt_node: str
    # ComfyUI node type + field whose value must appear in ComfyUI's
    # object_info for this engine to be considered available (e.g. a
    # checkpoint or unet file the user may not have downloaded yet).
    availability_check: tuple[str, str, str]  # (node_type, field, filename)
    negative_node: Optional[str] = None
    seed_nodes: list[str] = field(default_factory=list)
    field_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    # Node id of this engine's LoadImage node, if it supports IPAdapter
    # character-reference conditioning. None for engines that don't.
    reference_image_node: Optional[str] = None

    @property
    def supports_reference_image(self) -> bool:
        return self.reference_image_node is not None

    def build_workflow(
        self,
        prompt: str,
        negative: str,
        seed: int,
        reference_image_filename: Optional[str] = None,
    ) -> dict:
        workflow = json.loads((WORKFLOWS_DIR / self.workflow_file).read_text())
        for node_id, fields in self.field_overrides.items():
            workflow[node_id]["inputs"].update(fields)
        workflow[self.prompt_node]["inputs"]["text"] = prompt
        if self.negative_node:
            workflow[self.negative_node]["inputs"]["text"] = negative
        for node_id in self.seed_nodes:
            workflow[node_id]["inputs"]["seed"] = seed
        if self.reference_image_node:
            if not reference_image_filename:
                raise ValueError(
                    f"engine {self.id} requires a reference image but none was given"
                )
            workflow[self.reference_image_node]["inputs"]["image"] = (
                reference_image_filename
            )
        return workflow


ENGINES: dict[str, Engine] = {
    "flux_schnell": Engine(
        id="flux_schnell",
        label="FLUX.1 schnell",
        workflow_file="flux_schnell_api.json",
        output_node="9",
        prompt_node="6",
        seed_nodes=["13"],
        availability_check=("UNETLoader", "unet_name", FLUX_UNET_NAME),
        field_overrides={
            "12": {"unet_name": FLUX_UNET_NAME},
            "11": {"clip_name1": FLUX_CLIP_NAME1, "clip_name2": FLUX_CLIP_NAME2},
            "10": {"vae_name": FLUX_VAE_NAME},
        },
    ),
    "sdxl_adetailer": Engine(
        id="sdxl_adetailer",
        label="SDXL + ADetailer",
        workflow_file="sdxl_adetailer_api.json",
        output_node="11",
        prompt_node="2",
        negative_node="3",
        seed_nodes=["5", "8", "10"],
        availability_check=(
            "CheckpointLoaderSimple",
            "ckpt_name",
            "sd_xl_base_1.0.safetensors",
        ),
    ),
    "sdxl_adetailer_ipadapter": Engine(
        id="sdxl_adetailer_ipadapter",
        label="SDXL + ADetailer (character reference)",
        workflow_file="sdxl_adetailer_ipadapter_api.json",
        output_node="11",
        prompt_node="2",
        negative_node="3",
        seed_nodes=["5", "8", "10"],
        reference_image_node="14",
        availability_check=(
            "IPAdapterModelLoader",
            "ipadapter_file",
            "ip-adapter-plus_sdxl_vit-h.safetensors",
        ),
    ),
    "qwen_image_2512": Engine(
        id="qwen_image_2512",
        label="Qwen-Image-2512",
        workflow_file="qwen_image_2512_api.json",
        output_node="10",
        prompt_node="4",
        negative_node="5",
        seed_nodes=["8"],
        availability_check=(
            "UNETLoader",
            "unet_name",
            "qwen_image_2512_fp8_e4m3fn.safetensors",
        ),
    ),
}

DEFAULT_ENGINE_ID = os.environ.get("DEFAULT_IMAGE_ENGINE", "sdxl_adetailer")
