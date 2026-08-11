import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.agent import save_food_preference


def test_save_food_preference_add_memory() -> None:
    mock_context = MagicMock()
    mock_context.add_memory = AsyncMock()

    result = asyncio.run(save_food_preference("Alice is allergic to dairy", mock_context))

    assert "Saved food preference: Alice is allergic to dairy" in result
    mock_context.add_memory.assert_awaited_once()
    memories = mock_context.add_memory.call_args.kwargs["memories"]
    assert len(memories) == 1
    assert memories[0].content.parts[0].text == "Alice is allergic to dairy"


def test_save_food_preference_fallback_to_events() -> None:
    mock_context = MagicMock()
    mock_context.add_memory = AsyncMock(side_effect=NotImplementedError)
    mock_context.add_events_to_memory = AsyncMock()

    result = asyncio.run(save_food_preference("Bob dislikes spicy food", mock_context))

    assert "Saved food preference: Bob dislikes spicy food" in result
    mock_context.add_memory.assert_awaited_once()
    mock_context.add_events_to_memory.assert_awaited_once()
    events = mock_context.add_events_to_memory.call_args.kwargs["events"]
    assert len(events) == 1
    assert events[0].content.parts[0].text == "Bob dislikes spicy food"


def test_save_food_preference_value_error_fallback() -> None:
    mock_context = MagicMock()
    mock_context.add_memory = AsyncMock(side_effect=ValueError("Cannot add memory: memory service is not available."))
    mock_context.add_events_to_memory = AsyncMock()

    result = asyncio.run(save_food_preference("Charlie is gluten-free", mock_context))

    assert "Saved food preference: Charlie is gluten-free" in result
    mock_context.add_memory.assert_awaited_once()
    mock_context.add_events_to_memory.assert_awaited_once()
    events = mock_context.add_events_to_memory.call_args.kwargs["events"]
    assert len(events) == 1
    assert events[0].content.parts[0].text == "Charlie is gluten-free"
