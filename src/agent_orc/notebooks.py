"""Notebooks and their trash: what is deleted (a notebook, a folder, a note) waits there until it
is restored or deleted for good; nothing empties it by itself (Peuqui 06.11.2026)."""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

TrashKind = Literal["notebook", "folder", "note"]


class UnknownNotebookError(LookupError):
    """No notebook of this name."""


class NotebookExistsError(ValueError):
    """A notebook of this name exists already."""


class UnknownNoteError(LookupError):
    """No folder or note at this place of the notebook (another device changed it)."""


class UnknownNotesTrashEntryError(LookupError):
    """No entry of this id in the notes' trash."""


def _entry(
    kind: TrashKind, notebook: str, folder: str | None, content: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "kind": kind,
        "deleted_at": datetime.now(UTC).isoformat(),
        "notebook": notebook,
        # The folder a note was in; None for a loose note, a folder or a notebook.
        "folder": folder,
        "content": content,
    }


def _notebook(notebooks: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in notebooks:
        raise UnknownNotebookError(name)
    found: dict[str, Any] = notebooks[name]
    return found


def _pop(items: list[Any], index: int) -> Any:
    if not 0 <= index < len(items):
        raise UnknownNoteError(index)
    return items.pop(index)


def trash_notebook(notebooks: dict[str, Any], trash: list[dict[str, Any]], name: str) -> None:
    content = _notebook(notebooks, name)
    del notebooks[name]
    trash.insert(0, _entry("notebook", name, None, content))


def trash_folder(
    notebooks: dict[str, Any], trash: list[dict[str, Any]], name: str, folder: int
) -> None:
    content = _pop(_notebook(notebooks, name)["folders"], folder)
    trash.insert(0, _entry("folder", name, None, content))


def trash_note(
    notebooks: dict[str, Any],
    trash: list[dict[str, Any]],
    name: str,
    folder: int | None,
    note: int,
) -> None:
    """Moves a note to the trash: a loose one (folder None) or one of the folder at that index."""
    book = _notebook(notebooks, name)
    if folder is None:
        content, folder_name = _pop(book["notes"], note), None
    else:
        if not 0 <= folder < len(book["folders"]):
            raise UnknownNoteError(folder)
        place = book["folders"][folder]
        content, folder_name = _pop(place["notes"], note), place["name"]
    trash.insert(0, _entry("note", name, folder_name, content))


def _take(trash: list[dict[str, Any]], entry_id: str) -> dict[str, Any]:
    for index, entry in enumerate(trash):
        if entry["id"] == entry_id:
            taken: dict[str, Any] = trash.pop(index)
            return taken
    raise UnknownNotesTrashEntryError(entry_id)


def restore_trashed(
    notebooks: dict[str, Any], trash: list[dict[str, Any]], entry_id: str, name: str | None
) -> str:
    """Puts the entry back and returns the notebook it went into.

    A notebook comes back as the last tab, under `name` if given (its own is taken), otherwise
    its own. A folder or note goes back into its notebook, which is made again if it is gone; a
    note into its folder if there is one of that name, otherwise among the loose notes."""
    # Taken out first: on an error nothing is written back (state.changing_notes).
    entry = _take(trash, entry_id)
    if entry["kind"] == "notebook":
        target = name or entry["notebook"]
        if target in notebooks:
            raise NotebookExistsError(target)
        notebooks[target] = entry["content"]
    else:
        target = entry["notebook"]
        book = notebooks.setdefault(target, {"notes": [], "folders": []})
        if entry["kind"] == "folder":
            book["folders"].append(entry["content"])
        else:
            same = [folder for folder in book["folders"] if folder["name"] == entry["folder"]]
            (same[0]["notes"] if same else book["notes"]).append(entry["content"])
    return target


def delete_trashed(trash: list[dict[str, Any]], entry_id: str) -> None:
    _take(trash, entry_id)
