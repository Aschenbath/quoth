"""Load a safetensors checkpoint as memory-mapped views instead of copies.

Every weight becomes a view into the file on disk, so the operating system
pages in only what a forward pass touches. This is what makes Gemma 4 E4B
usable on a laptop with ~10 GB of free RAM: about 5.6 GB of its 16 GB checkpoint
is a per-layer embedding table that is only ever indexed by the input tokens,
plus audio and vision encoders a text-only probe never calls.
"""

from __future__ import annotations

import json
import mmap
import struct
import warnings
from pathlib import Path

import torch

DTYPES = {"BF16": torch.bfloat16, "F16": torch.float16, "F32": torch.float32,
          "I64": torch.int64, "I32": torch.int32, "BOOL": torch.bool, "U8": torch.uint8}


def mmap_safetensors(path: Path) -> dict[str, torch.Tensor]:
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
        # read-only mapping: no commit charge, pages are shared with the file cache
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    out = {}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="The given buffer is not writable")
        for name, info in header.items():
            if name == "__metadata__":
                continue
            a, b = info["data_offsets"]
            dt = DTYPES[info["dtype"]]
            t = torch.frombuffer(mm, dtype=dt, count=(b - a) // dt.itemsize, offset=8 + n + a)
            out[name] = t.view(info["shape"])
    return out


def _rebuild_meta_buffers(model: torch.nn.Module) -> list[str]:
    """Modules built on the meta device have meta buffers (rotary tables, scales).
    Recompute the ones the text path uses; report any left behind."""
    from transformers.models.gemma4 import modeling_gemma4 as g4

    for name, mod in list(model.named_modules()):
        if isinstance(mod, g4.Gemma4TextRotaryEmbedding) and any(b.is_meta for b in mod.buffers()):
            with torch.device("cpu"):
                fresh = g4.Gemma4TextRotaryEmbedding(mod.config, device="cpu")
            parent, _, attr = name.rpartition(".")
            setattr(model.get_submodule(parent) if parent else model, attr, fresh)
        elif isinstance(mod, g4.Gemma4TextScaledWordEmbedding) and mod.embed_scale.is_meta:
            mod.embed_scale = torch.tensor(mod.scalar_embed_scale)
    return [f"{m}.{b}" for m, mod in model.named_modules() for b, t in mod._buffers.items()
            if t is not None and t.is_meta]


def load_mmapped(path: str, dtype: torch.dtype = torch.bfloat16) -> torch.nn.Module:
    from transformers import AutoConfig, AutoModelForCausalLM

    config = AutoConfig.from_pretrained(path)
    with torch.device("meta"):
        model = AutoModelForCausalLM.from_config(config, dtype=dtype)
    state = {}
    for f in sorted(Path(path).glob("*.safetensors")):
        state.update(mmap_safetensors(f))
    if any(t.dtype != dtype for t in state.values() if t.is_floating_point()):
        raise ValueError("checkpoint dtype differs from requested dtype; mmap loading cannot convert")
    missing, unexpected = model.load_state_dict(state, strict=False, assign=True)
    model.tie_weights()
    missing = [k for k in missing if k.removesuffix(".weight") != "lm_head"]
    if missing:
        raise ValueError(f"weights missing from checkpoint: {missing[:5]}")
    # Gemma 4 checkpoints also store k/v projections for layers that reuse an
    # earlier layer's KV cache; the model has no slot for them and never uses them.
    stray = [k for k in unexpected if not k.endswith(("k_proj.weight", "v_proj.weight", "k_norm.weight"))]
    if stray:
        raise ValueError(f"unexpected checkpoint keys: {stray[:5]}")
    leftover = _rebuild_meta_buffers(model)
    text_left = [b for b in leftover if "audio" not in b and "vision" not in b]
    if text_left:
        raise ValueError(f"meta buffers left on the text path: {text_left}")
    return model.eval()
