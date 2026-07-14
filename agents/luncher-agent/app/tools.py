"""Tools for the Luncher Meeting and Catering Agent.

This file provides the core tooling integrations for:
1. RAG Document Grounding (meeting guidelines)
2. Calendar Free/Busy checks
3. Catering Vendor and Menu search (via REST or MCP)
4. Placing final orders
"""

import json
import urllib.request
import urllib.error
import os

# Base URL for the mock Luncher API backend
BACKEND_URL = os.environ.get("LUNCHER_BACKEND_URL", "http://localhost:8080")


def query_agenda_guidelines(query: str) -> str:
    """Searches the corporate meeting guidelines for compliance, agenda templates, and budget rules.

    Args:
        query: Search keywords or question about corporate meeting templates and catering rules.

    Returns:
        Relevant excerpt text from the company guidelines document.
    """
    # For a real RAG scenario, this would call agents-cli data-ingestion / vector search.
    # To ensure a zero-setup local fallback for testing, we read the guideline document directly.
    guideline_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../docs/meeting_guidelines.md"))
    try:
        with open(guideline_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"[GROUNDING RESOURCE: docs/meeting_guidelines.md]\n\n{content}"
    except Exception as e:
        return f"Error loading grounding guidelines: {str(e)}"


def get_calendar_availability(attendees: list[str]) -> str:
    """Queries corporate schedules to find free/busy times for specific attendees.

    Args:
        attendees: List of employee names (e.g., ["Alice", "Bob"]).

    Returns:
        A JSON string containing calendar busy windows for each requested employee.
    """
    url = f"{BACKEND_URL}/calendar"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
        
        # Filter calendar only for the requested attendees
        filtered = {name: res_data.get(name, []) for name in attendees if name in res_data}
        if not filtered:
            return f"No calendar logs found for requested employees: {attendees}"
        return json.dumps(filtered, indent=2)
    except urllib.error.URLError as e:
        return f"Calendar Service Unavailable. Ensure backend is running. Error: {str(e.reason)}"


def search_catering(cuisine: str) -> str:
    """Searches approved corporate catering vendors and menu options by cuisine.

    Args:
        cuisine: The desired cuisine type (e.g., 'Healthy', 'Burgers', 'Asian').

    Returns:
        JSON list of vendors matching the requested cuisine, including ratings, menus, and prices.
    """
    # --- MCP SERVER EXTENSION EXERCISE TIP ---
    # In Exercise 2 & 3, instead of calling this local python function, this tool
    # can be discovered and hosted dynamically through the Luncher MCP server,
    # registering the schema from the Flask /catering REST contracts directly!
    # ------------------------------------------
    url = f"{BACKEND_URL}/catering"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
        
        # Filter by cuisine (case-insensitive)
        matched = [v for v in res_data if v.get("cuisine", "").lower() == cuisine.lower()]
        if not matched:
            # Return all vendors if no direct match is found
            return json.dumps(res_data, indent=2)
        return json.dumps(matched, indent=2)
    except urllib.error.URLError as e:
        return f"Catering Service Unavailable. Ensure backend is running on {BACKEND_URL}. Error: {str(e.reason)}"


def submit_catering_order(restaurant: str, items: list[str], total_cost: float) -> str:
    """Places a draft catering order with the specified vendor.

    Args:
        restaurant: Name of the catering vendor (e.g., 'Vibrant Salad Bar').
        items: List of food item names to order.
        total_cost: Expected total cost of the order.

    Returns:
        Confirmation receipt details including order status and a tracking ID.
    """
    url = f"{BACKEND_URL}/orders"
    payload = {
        "restaurant": restaurant,
        "items": items,
        "total_cost": total_cost
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
        return json.dumps(res_data, indent=2)
    except urllib.error.URLError as e:
        return f"Catering Order submission failed. Ensure backend is running. Error: {str(e.reason)}"
