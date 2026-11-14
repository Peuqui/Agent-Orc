"""What a llama-swap on this machine tells about its models: which ones serve a conversation, and
the reasoning levels each takes, read from its chat template.

llama-swap starts a model with the command in its configuration, which names the model: a
checkpoint folder (vLLM) or a GGUF file (llama.cpp). The chat template in it renders the prompt,
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

import gguf
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
# Where a GGUF file keeps its template (for a split one: its first part, which llama-swap names).
GGUF_TEMPLATE_FIELD = "tokenizer.chat_template"
# What precedes the model in a server's command: llama.cpp's and vLLM's option, `vllm serve`.
MODEL_MARKERS = ("--model", "serve")
# A server started with one of these computes embeddings and holds no conversation (llama.cpp).
EMBEDDING_FLAGS = ("--embedding", "--embeddings")
# Or with one of these options and values (vLLM: older --task, newer --runner).
EMBEDDING_OPTIONS = {"--task": "embed", "--runner": "pooling"}
# How far the branch of a comparison may reach to the assignment that renames its level.
REMAP_REACH = 60


class LlamaSwapError(RuntimeError):
    """What llama-swap's configuration or a model's template does not tell, said as it is."""


def commands(llama_swap_config: Path) -> dict[str, list[str]]:
    """Each model's command in llama-swap's configuration, split into its arguments."""
    try:
        models = yaml.safe_load(llama_swap_config.read_text(encoding="utf-8"))["models"]
        return {name: shlex.split(entry["cmd"]) for name, entry in models.items()}
    except (OSError, yaml.YAMLError, KeyError, TypeError, ValueError) as error:
        raise LlamaSwapError(f"llama-swap's configuration {llama_swap_config}: {error}") from error


def serves_embeddings(command: list[str]) -> bool:
    """Whether the server the command starts computes embeddings instead of answering."""
    if any(flag in command for flag in EMBEDDING_FLAGS):
        return True
    return any(
        command[index + 1] == value
        for index, argument in enumerate(command[:-1])
        if (value := EMBEDDING_OPTIONS.get(argument)) is not None
    )


def embedding_models(llama_swap_config: Path) -> set[str]:
    """The models of llama-swap that compute embeddings: no conversation to have with them."""
    return {
        name for name, command in commands(llama_swap_config).items() if serves_embeddings(command)
    }


def model_path(llama_swap_config: Path, model: str) -> Path:
    """What llama-swap's command for the model names as its model: after `--model` (llama.cpp,
    vLLM's API server) or after `vllm serve`."""
    known = commands(llama_swap_config)
    if model not in known:
        raise LlamaSwapError(f"{model} is not in llama-swap's configuration {llama_swap_config}")
    command = known[model]
    for marker in MODEL_MARKERS:
        if marker in command[:-1]:
            return Path(command[command.index(marker) + 1])
    raise LlamaSwapError(
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


def gguf_template(path: Path) -> str:
    """The template a GGUF file carries; empty when it carries none."""
    try:
        field = gguf.GGUFReader(path).fields.get(GGUF_TEMPLATE_FIELD)
    except (OSError, ValueError) as error:
        raise LlamaSwapError(f"the GGUF file {path} cannot be read: {error}") from error
    return "" if field is None else bytes(field.parts[field.data[0]]).decode("utf-8")


def template_levels(llama_swap_config: Path, model: str) -> list[str]:
    """The levels a model of llama-swap takes, from its chat template; none for a model whose
    template has no levels (it thinks without being told how much, or not at all)."""
    path = model_path(llama_swap_config, model)
    if path.is_file():
        return detect_levels(gguf_template(path))
    if not path.is_dir():
        raise LlamaSwapError(f"the model of {model} is not there: {path}")
    levels = detect_levels(checkpoint_template(path))
    return levels or detect_levels(prompt_encoder(path))
