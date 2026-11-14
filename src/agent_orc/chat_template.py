"""The reasoning levels a local model takes, read from its chat template.

llama-swap starts a model with the command in its configuration; `--model` there names the model:
a checkpoint folder (vLLM) or a GGUF file (llama.cpp). The chat template in it renders the prompt,
and the levels it takes are those it compares `reasoning_effort` with. A level it does not know
makes it refuse the request (the Qwen3.8 template raises an exception, the DeepSeek-V4 encoder
fails an assert), so the levels on offer must be exactly these.

The detection is AIfred's (aifred/lib/gguf_utils.py, detect_reasoning_levels), with one
difference: the assert lines of a prompt encoder count. AIfred offers "on" (no level sent) beside
the levels and leaves out a level that renders the same prompt as that one; Claude Code always
sends a level, so a level the model takes counts even when it changes nothing (DeepSeek-V4: high,
its plain thinking, beside max).
"""

import json
import re
import shlex
from pathlib import Path

import yaml

from agent_orc.config import LEVELS

# The variable Claude Code's level reaches the template as (chat_template_kwargs).
LEVEL_VARIABLE = "reasoning_effort"
# The two places transformers keeps a checkpoint's template.
TEMPLATE_FILE = "chat_template.jinja"
TOKENIZER_CONFIG_FILE = "tokenizer_config.json"
# DeepSeek checkpoints render their prompt with a bundled encoder in Python, which vLLM calls
# instead of a Jinja template.
ENCODER_PATTERN = "encoding/encoding_*.py"
# What precedes the model in a server's command: llama.cpp's and vLLM's option, `vllm serve`.
MODEL_MARKERS = ("--model", "serve")
# How far the branch of a comparison may reach to the assignment that renames its level.
REMAP_REACH = 60


class TemplateError(RuntimeError):
    """The template of a model cannot be read, said to the user as it is."""


def model_path(llama_swap_config: Path, model: str) -> Path:
    """What llama-swap's command for the model names as its model: after `--model` (llama.cpp,
    vLLM's API server) or after `vllm serve`."""
    try:
        models = yaml.safe_load(llama_swap_config.read_text(encoding="utf-8"))["models"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as error:
        raise TemplateError(f"llama-swap's configuration {llama_swap_config}: {error}") from error
    if model not in models:
        raise TemplateError(f"{model} is not in llama-swap's configuration {llama_swap_config}")
    command = shlex.split(models[model]["cmd"])
    for marker in MODEL_MARKERS:
        if marker in command[:-1]:
            return Path(command[command.index(marker) + 1])
    raise TemplateError(
        f"the command of {model} in {llama_swap_config} names no model"
        f" (after {' or '.join(MODEL_MARKERS)})"
    )


def checkpoint_template(checkpoint: Path) -> str:
    """The Jinja template of a checkpoint folder; empty when it has none."""
    template_file = checkpoint / TEMPLATE_FILE
    if template_file.exists():
        return template_file.read_text(encoding="utf-8")
    tokenizer_config = checkpoint / TOKENIZER_CONFIG_FILE
    if not tokenizer_config.exists():
        return ""
    template = json.loads(tokenizer_config.read_text(encoding="utf-8")).get("chat_template") or ""
    if isinstance(template, list):
        # Named templates (default, tool_use, ...): all of them count.
        return "\n".join(str(named.get("template", "")) for named in template)
    return str(template)


def prompt_encoder(checkpoint: Path) -> str:
    """The source of the checkpoint's bundled prompt encoder; empty when it has none."""
    encoders = sorted(checkpoint.glob(ENCODER_PATTERN))
    return encoders[0].read_text(encoding="utf-8") if encoders else ""


def detect_levels(template: str) -> list[str]:
    """The levels of Claude Code the template takes, from the lowest up: those it compares the
    level variable with (also under a name it renames it to), and the one it falls back to when
    none is sent. A level the template turns into another one before any comparison is that one."""
    found: set[str] = set()
    names = [LEVEL_VARIABLE]
    # {%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %} (Qwen3.8), or
    # ... if reasoning_effort in ['low', 'high'] else 'max' (GLM-5.3): the comparisons then run
    # on that name, and the literal it falls back to is a level of its own.
    for match in re.finditer(rf"\bset\s+(\w+)\s*=\s*({LEVEL_VARIABLE}\b[^%]*)", template):
        if match.group(1) not in names:
            names.append(match.group(1))
        fallback = re.search(
            r"\|\s*default\(\s*['\"]([\w-]+)['\"]|\belse\s+['\"]([\w-]+)['\"]", match.group(2)
        )
        if fallback:
            found.add(fallback.group(1) or fallback.group(2))
    for name in names:
        variable = re.escape(name)
        # name == 'max', name != "high", 'max' == name
        found.update(re.findall(rf"(?<!\w){variable}\s*[=!]=\s*['\"]([\w-]+)['\"]", template))
        found.update(re.findall(rf"['\"]([\w-]+)['\"]\s*[=!]=\s*{variable}(?!\w)", template))
        # name in ['low', 'high'], name not in ('xhigh', 'medium', 'low')
        for listed in re.findall(
            rf"(?<!\w){variable}\s+(?:not\s+)?in\s*[\[\(]([^\]\)]*)[\]\)]", template
        ):
            found.update(re.findall(r"['\"]([\w-]+)['\"]", listed))
    # {%- if name == 'high' %}{%- set name = 'xhigh' %}: high renders what xhigh renders.
    for name in names:
        variable = re.escape(name)
        for source, target in re.findall(
            rf"(?<!\w){variable}\s*==\s*['\"]([\w-]+)['\"].{{0,{REMAP_REACH}}}?"
            rf"set\s+{variable}\s*=\s*['\"]([\w-]+)['\"]",
            template,
            re.DOTALL,
        ):
            if source != target:
                found.discard(source)
    return [level for level in LEVELS if level in found]


def template_levels(llama_swap_config: Path, model: str) -> list[str]:
    """The levels a model of llama-swap takes, from its chat template; none for a model whose
    template has no levels (it thinks without being told how much, or not at all)."""
    path = model_path(llama_swap_config, model)
    if not path.is_dir():
        raise TemplateError(
            f"the template of {model} cannot be read: {path} is no checkpoint folder"
        )
    levels = detect_levels(checkpoint_template(path))
    return levels or detect_levels(prompt_encoder(path))
