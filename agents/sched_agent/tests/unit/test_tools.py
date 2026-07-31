import json
import os
import pytest
from app.tools import (
    get_team_members,
    get_catering_options,
    book_meeting,
    update_team_member_preferences,
)


def test_get_team_members() -> None:
    members = get_team_members()
    assert isinstance(members, list)
    assert len(members) > 0
    names = [m["name"] for m in members]
    assert "Alice" in names
    assert "Bob" in names


def test_get_catering_options() -> None:
    options = get_catering_options()
    assert isinstance(options, list)
    assert len(options) > 0
    names = [c["name"] for m in options for c in [m]]
    assert "Fiesta Tacos" in names or "Green Garden" in names


def test_book_meeting_and_preferences(tmp_path: pytest.TempPathFactory) -> None:
    res = book_meeting("Monday 10:00-11:00 AM", "Fiesta Tacos", "Test booking")
    assert "Successfully booked!" in res

    pref_res = update_team_member_preferences(
        name="Alice",
        preferred_time_of_day="afternoon",
        dietary_restrictions=["Vegan", "Nut-Free"],
    )
    assert "Successfully updated central database" in pref_res
