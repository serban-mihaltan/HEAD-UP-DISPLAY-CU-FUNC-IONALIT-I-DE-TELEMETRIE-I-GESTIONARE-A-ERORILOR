from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class GaugeBand:
    """
    Represent the GaugeBand component in the HUD application.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    start_rpm: int
    end_rpm: int
    start_redline: bool
    end_redline: bool


def clamp(value: float, low: float, high: float) -> float:
    """
    Constrain a value to a minimum and maximum range.

    Implementation details:
        Compares the input against both bounds and returns the nearest valid value.
    """
    return max(low, min(high, value))


def ratio(value: float, maximum: float) -> float:
    """
    Normalize a value into a zero-to-one range.

    Implementation details:
        Clamps the input range first, then divides by the span to produce a normalized value.
    """
    maximum = max(maximum, 1.0)
    return clamp(value / maximum, 0.0, 1.0)


def digital_rpm_bands(max_rpm: int, redline_rpm: int) -> list[GaugeBand]:
    """
    Return RPM color bands for the digital RPM display.

    Implementation details:
        Uses the object state and supplied arguments to compute and return the required result.
    """
    bands: list[GaugeBand] = []
    step = 500
    for start in range(0, max_rpm, step):
        end = min(max_rpm, start + step)
        bands.append(
            GaugeBand(
                start_rpm=start,
                end_rpm=end,
                start_redline=start >= redline_rpm,
                end_redline=end > redline_rpm,
            )
        )
    return bands


def label_color_is_red(label_rpm: int, redline_rpm: int) -> bool:
    """
    Determine whether a numeric label should use the redline color.

    Implementation details:
        Uses the object state and supplied arguments to compute and return the required result.
    """
    return label_rpm > redline_rpm or (label_rpm == redline_rpm and label_rpm != 0)
