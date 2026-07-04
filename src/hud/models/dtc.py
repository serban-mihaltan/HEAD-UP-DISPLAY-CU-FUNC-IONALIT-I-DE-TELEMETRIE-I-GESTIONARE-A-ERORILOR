from __future__ import annotations

from dataclasses import dataclass

from hud.models.enums import DtcCategory


@dataclass(slots=True)
class DtcEntry:
    """
    Store one diagnostic trouble code entry for display and clearing actions.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    category: DtcCategory
    code: str
    description: str
    raw_payload: str = ""
