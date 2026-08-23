import json
from typing import Any


def extract_products(state):
    products = []
    active_filters = state.get("active_filters", {})

    for message in reversed(state["messages"]):
        if getattr(message, "type", None) != "tool":
            continue

        if getattr(message, "name", None) != "search_catalog":
            continue

        try:
            data = json.loads(message.content)
        except (TypeError, json.JSONDecodeError):
            continue

        results = data.get("results", [])

        if results:
            products = [
                item["product"]
                for item in results
                if "product" in item
            ]

            # Find the AI message that produced this tool call.
            tool_call_id = getattr(message, "tool_call_id", None)

            if tool_call_id:
                for previous in reversed(state["messages"]):
                    tool_calls = getattr(previous, "tool_calls", [])

                    for tool_call in tool_calls:
                        if tool_call.get("id") == tool_call_id:
                            args = tool_call.get("args", {})

                            active_filters = {
                                key: value
                                for key, value in args.items()
                                if key != "query"
                            }

                            break

                    if active_filters:
                        break

            break

    return {
        "products": products,
        "active_filters": active_filters,
    }