"""The levels a local model takes, read from its chat template through llama-swap's command."""

import json
from pathlib import Path

import pytest

from agent_orc.chat_template import (
    TemplateError,
    detect_levels,
    model_path,
    template_levels,
)

# The lines of the real templates that decide the level (November 2026).
QWEN38 = """
{%- if enable_thinking is undefined or enable_thinking is true %}
    {%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}
    {%- if resolved_reasoning_effort not in ('xhigh', 'medium', 'low') %}
        {{- raise_exception('Unexpected reasoning effort ' ~ reasoning_effort ~ '.') }}
    {%- endif %}
    {%- if resolved_reasoning_effort == 'xhigh' %}
    {%- elif resolved_reasoning_effort == 'low' %}
    {%- endif %}
{%- endif %}
"""
GLM53 = (
    "{%- set effective_reasoning_effort = reasoning_effort if reasoning_effort is defined and "
    "reasoning_effort in ['low', 'high'] else 'max' -%}\n"
    "{%- if effective_reasoning_effort is not none -%}<|system|>Reasoning Effort: "
    "{{ effective_reasoning_effort | capitalize }}{%- endif -%}\n"
)
DEEPSEEK_V4_ENCODER = """
REASONING_EFFORT_MAX = ("...")

def render_message(index, messages, thinking_mode, reasoning_effort=None):
    \"\"\"reasoning_effort: Optional reasoning effort level ("max", "high", or None).\"\"\"
    assert reasoning_effort in ['max', None, 'high'], f"Invalid: {reasoning_effort}"
    if index == 0 and thinking_mode == "thinking" and reasoning_effort == 'max':
        prompt += REASONING_EFFORT_MAX
"""


def test_qwen_takes_its_listed_levels_and_its_default() -> None:
    assert detect_levels(QWEN38) == ["low", "medium", "xhigh"]


def test_glm_takes_its_listed_levels_and_what_it_falls_back_to() -> None:
    assert detect_levels(GLM53) == ["low", "high", "max"]


def test_deepseek_takes_what_its_encoder_asserts_also_where_it_changes_nothing() -> None:
    # high renders the plain thinking; Claude Code always sends a level, so it must be there.
    assert detect_levels(DEEPSEEK_V4_ENCODER) == ["high", "max"]


def test_a_level_the_template_turns_into_another_one_is_that_one() -> None:
    template = (
        "{%- if reasoning_effort == 'high' %}{%- set reasoning_effort = 'xhigh' %}{%- endif %}"
        "{%- if reasoning_effort == 'xhigh' %}...{%- elif reasoning_effort == 'low' %}..."
    )
    assert detect_levels(template) == ["low", "xhigh"]


def test_names_that_are_no_level_of_claude_code_are_left_out() -> None:
    template = "{%- if reasoning_effort in ['none', 'minimal', 'low'] %}"
    assert detect_levels(template) == ["low"]


def test_a_template_without_levels_has_none() -> None:
    assert detect_levels("{%- if enable_thinking %}<think>{%- endif %}") == []
    # The variable with a longer name is another one (DeepSeek's prompt text).
    assert detect_levels("{{ reasoning_effort_max == 'max' }}") == []


def llama_swap(tmp_path: Path, commands: dict[str, str]) -> Path:
    config = tmp_path / "llama-swap.yaml"
    models = "".join(f"  {name}:\n    cmd: {command}\n" for name, command in commands.items())
    config.write_text(f"models:\n{models}", encoding="utf-8")
    return config


def checkpoint(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    folder = tmp_path / name
    for relative, text in files.items():
        (folder / relative).parent.mkdir(parents=True, exist_ok=True)
        (folder / relative).write_text(text, encoding="utf-8")
    return folder


def test_the_model_is_what_llama_swaps_command_names_with_model(tmp_path: Path) -> None:
    command = (
        "/vllm/bin/python -m vllm.entrypoints.openai.api_server --model /models/q --port ${PORT} "
        "--speculative-config '{\"method\": \"mtp\"}'"
    )
    serve = "/vllm/bin/vllm serve /models/s --served-model-name s-vllm --port ${PORT}"
    config = llama_swap(tmp_path, {"q-vllm": json.dumps(command), "s-vllm": serve})
    assert model_path(config, "q-vllm") == Path("/models/q")
    assert model_path(config, "s-vllm") == Path("/models/s")


def test_a_model_llama_swap_does_not_know_or_without_model_is_said(tmp_path: Path) -> None:
    config = llama_swap(tmp_path, {"plain": "/bin/server --port ${PORT}"})
    with pytest.raises(TemplateError, match="other is not in llama-swap's configuration"):
        model_path(config, "other")
    with pytest.raises(TemplateError, match="names no model"):
        model_path(config, "plain")
    with pytest.raises(TemplateError, match="missing.yaml"):
        model_path(tmp_path / "missing.yaml", "plain")


def test_the_levels_come_from_the_jinja_file_or_the_tokenizer_config(tmp_path: Path) -> None:
    jinja = checkpoint(tmp_path, "qwen", {"chat_template.jinja": QWEN38})
    tokenizer = checkpoint(
        tmp_path, "glm", {"tokenizer_config.json": json.dumps({"chat_template": GLM53})}
    )
    named = checkpoint(
        tmp_path,
        "named",
        {"tokenizer_config.json": json.dumps({"chat_template": [{"template": QWEN38}]})},
    )
    config = llama_swap(
        tmp_path,
        {name: f"server --model {folder}" for name, folder in
         {"qwen": jinja, "glm": tokenizer, "named": named}.items()},
    )
    assert template_levels(config, "qwen") == ["low", "medium", "xhigh"]
    assert template_levels(config, "glm") == ["low", "high", "max"]
    assert template_levels(config, "named") == ["low", "medium", "xhigh"]


def test_without_levels_in_its_template_a_checkpoint_has_its_encoders(tmp_path: Path) -> None:
    folder = checkpoint(
        tmp_path,
        "deepseek",
        {
            "tokenizer_config.json": json.dumps({"chat_template": None}),
            "encoding/encoding_dsv4.py": DEEPSEEK_V4_ENCODER,
        },
    )
    plain = checkpoint(tmp_path, "plain", {"chat_template.jinja": "{{ messages }}"})
    config = llama_swap(
        tmp_path, {"deepseek": f"server --model {folder}", "plain": f"server --model {plain}"}
    )
    assert template_levels(config, "deepseek") == ["high", "max"]
    assert template_levels(config, "plain") == []


def test_a_model_that_is_no_checkpoint_folder_is_said(tmp_path: Path) -> None:
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"GGUF")
    config = llama_swap(tmp_path, {"gguf": f"server --model {gguf}"})
    with pytest.raises(TemplateError, match="is no checkpoint folder"):
        template_levels(config, "gguf")
