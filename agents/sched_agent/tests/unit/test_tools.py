import json
import os
import pytest
from app.tools import (
    get_team_members,
    book_meeting,
)


def test_get_team_members() -> None:
    members = get_team_members()
    assert isinstance(members, list)
    assert len(members) == 8
    names = [m["name"] for m in members]
    assert "Liam" in names
    assert "Maya" in names

    # Ensure dietary restrictions and cuisine preferences are stripped
    for member in members:
        assert "dietary_restrictions" not in member
        assert "cuisine_preferences" not in member
        assert "timezone" in member
        assert "weekly_availability" in member


def test_book_meeting(tmp_path: pytest.TempPathFactory) -> None:
    res = book_meeting("Monday 10:00-11:00 AM", "Fiesta Tacos", "Test booking")
    assert "Successfully booked!" in res
