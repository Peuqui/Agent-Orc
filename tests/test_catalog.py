"""The model catalogs of other machines, as kept here, and the backends that take theirs."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from agent_orc.backends import (
    BackendError,
    levels_of,
    offered,
    prepare_launch,
    served_catalog,
    ttl_of,
)
from agent_orc.catalog import (
    CatalogBackend,
    CatalogError,
    CatalogModel,
    UnknownMachineError,
    read_catalog,
    store_catalog,
)
from agent_orc.config import BackendConfig, Config, default_config_text, parse_config

TODAY = date(2026, 11, 14)
MINI_LOCAL = CatalogBackend(
    models=[
        CatalogModel(name="DeepSeek-vllm", levels=["high", "max"], ttl=900),
        CatalogModel(name="Instruct-gguf"),
        CatalogModel(name="Broken-vllm", problem="its template cannot be read"),
    ]
)


def remote_backend(**changes: Any) -> BackendConfig:
    fields: dict[str, Any] = {
        "label": "Local models of the Mini",
        "base_urls": ["http://mini"],
        "key": "no-key",
        "catalog_from": {"machine": "Mini", "backend": "local"},
    }
    return BackendConfig.model_validate({**fields, **changes})


def test_a_catalog_is_kept_under_the_name_of_its_machine() -> None:
    store_catalog("Mini", {"local": MINI_LOCAL})
    assert read_catalog("Mini").backends == {"local": MINI_LOCAL}
    with pytest.raises(CatalogError, match="no catalog from Aragon here yet"):
        read_catalog("Aragon")
    # A name is part of a file name here: no path in it.
    with pytest.raises(UnknownMachineError):
        store_catalog("../Mini", {})


def test_a_backend_on_another_machine_offers_what_its_catalog_lists() -> None:
    store_catalog("Mini", {"local": MINI_LOCAL})
    backend = remote_backend()
    listed = ["Instruct-gguf", "DeepSeek-vllm", "Not-in-the-catalog", "Broken-vllm"]
    assert offered(listed, backend, TODAY) == ["Broken-vllm", "DeepSeek-vllm", "Instruct-gguf"]
    assert levels_of(backend, "DeepSeek-vllm") == ["high", "max"]
    assert levels_of(backend, "Instruct-gguf") == []
    with pytest.raises(BackendError, match="Mini cannot tell the levels of Broken-vllm"):
        levels_of(backend, "Broken-vllm")
    with pytest.raises(BackendError, match="Not-in-the-catalog is not in the catalog from Mini"):
        levels_of(backend, "Not-in-the-catalog")


def test_the_ttl_of_a_model_on_another_machine_comes_from_its_catalog() -> None:
    store_catalog("Mini", {"local": MINI_LOCAL})
    backend = remote_backend()
    assert ttl_of(backend, "DeepSeek-vllm") == 900
    assert ttl_of(backend, "Instruct-gguf") is None
    with pytest.raises(BackendError, match="Mini cannot tell the ttl of Broken-vllm"):
        ttl_of(backend, "Broken-vllm")
    with pytest.raises(BackendError, match="Not-in-the-catalog is not in the catalog from Mini"):
        ttl_of(backend, "Not-in-the-catalog")
    # Neither a llama-swap here nor a catalog: nothing tells it.
    assert ttl_of(remote_backend(catalog_from=None), "DeepSeek-vllm") is None


def test_the_start_on_another_machines_model_takes_its_levels() -> None:
    store_catalog("Mini", {"local": MINI_LOCAL})

    def fetch(url: str, key: str | None, timeout: float) -> Any:
        assert url == "http://mini/v1/models"
        return {"data": [{"id": "DeepSeek-vllm"}]}

    launch = prepare_launch("local", remote_backend(), "DeepSeek-vllm", "low", [], TODAY, fetch)
    assert launch.command[-2:] == ["--effort", "high"]


def test_what_the_catalog_does_not_tell_is_said() -> None:
    with pytest.raises(CatalogError, match="no catalog from Mini here yet"):
        offered(["DeepSeek-vllm"], remote_backend(), TODAY)
    store_catalog("Mini", {"cloud": CatalogBackend(), "local": CatalogBackend(problem="down")})
    with pytest.raises(BackendError, match="Mini cannot list the models of its backend local"):
        offered(["DeepSeek-vllm"], remote_backend(), TODAY)
    elsewhere = remote_backend(catalog_from={"machine": "Mini", "backend": "other"})
    with pytest.raises(BackendError, match="the catalog from Mini has no backend other"):
        offered(["DeepSeek-vllm"], elsewhere, TODAY)


def test_the_levels_come_from_one_place() -> None:
    with pytest.raises(ValidationError, match="not both"):
        remote_backend(llama_swap_config="~/llama-swap.yaml")
    with pytest.raises(ValidationError, match="give no levels in models"):
        remote_backend(models={"m": {"levels": ["low"]}})


def test_this_machines_catalog_holds_the_backends_it_reads_itself(tmp_path: Path) -> None:
    checkpoint = tmp_path / "qwen"
    checkpoint.mkdir()
    (checkpoint / "chat_template.jinja").write_text(
        "{%- if reasoning_effort in ['low', 'xhigh'] %}", encoding="utf-8"
    )
    llama_swap = tmp_path / "llama-swap.yaml"
    llama_swap.write_text(
        f"models:\n  qwen:\n    cmd: vllm serve {checkpoint}\n    ttl: 900\n"
        f"  gone:\n    cmd: vllm serve {tmp_path / 'gone'}\n",
        encoding="utf-8",
    )
    config = Config.model_validate(
        {
            **parse_config(default_config_text()).model_dump(),
            "backends": {
                "local": {
                    "label": "Local",
                    "base_urls": ["http://here"],
                    "key": "no-key",
                    "llama_swap_config": str(llama_swap),
                },
                "down": {
                    "label": "Down",
                    "base_urls": ["http://nowhere"],
                    "key": "no-key",
                    "llama_swap_config": str(llama_swap),
                },
                "cloud": {"label": "Cloud", "base_urls": ["http://cloud"], "key": "k"},
            },
        }
    )

    def fetch(url: str, key: str | None, timeout: float) -> Any:
        if url.startswith("http://here"):
            return {"data": [{"id": "qwen"}, {"id": "gone"}]}
        raise OSError("no answer")

    catalog = served_catalog(config, TODAY, fetch)
    # A cloud backend is not read here: its models stay where they are configured.
    assert set(catalog) == {"local", "down"}
    assert catalog["local"].models[1] == CatalogModel(name="qwen", levels=["low", "xhigh"], ttl=900)
    assert catalog["local"].models[0].name == "gone"
    assert "is not there" in (catalog["local"].models[0].problem or "")
    assert "does not answer at http://nowhere" in (catalog["down"].problem or "")
