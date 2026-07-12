from google.adk.agents import Agent

def get_recommended_lunches() -> list[dict]:
    """Returns the list of recommended team lunch restaurants with their cuisine and ratings."""
    return [
        {"id": 1, "name": "Antigravity Burger Joint", "cuisine": "Burgers", "rating": 4.9},
        {"id": 2, "name": "Vibrant Salad Bar", "cuisine": "Healthy", "rating": 4.7},
        {"id": 3, "name": "Taco Time", "cuisine": "Mexican", "rating": 4.8},
        {"id": 4, "name": "Noodle Nest", "cuisine": "Asian", "rating": 4.6}
    ]

root_agent = Agent(
    model="gemini-2.5-flash",
    name="luncher_agent",
    description="The Luncher Assistant that helps teams find and select the best lunch options.",
    instruction=(
        "You are the Luncher Assistant. Your job is to help users select the best team lunch "
        "options. You have access to the 'get_recommended_lunches' tool to retrieve live recommendations. "
        "Provide enthusiastic, helpful advice on which restaurant to choose based on user preferences."
    ),
    tools=[get_recommended_lunches]
)
