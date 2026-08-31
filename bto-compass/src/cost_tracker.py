# src/cost_tracker.py
class UsageTracker:
    def __init__(self):
        # Rates per 1M tokens (USD)
        self.input_rate = 3.00
        self.output_rate = 15.00
        self.cache_write_rate = 3.75
        self.cache_read_rate = 0.30

    def calculate_cost(self, usage: dict) -> float:
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        cache_write = usage.get("cache_creation_input_tokens", 0) or 0
        cache_read = usage.get("cache_read_input_tokens", 0) or 0

        cost = (
            (input_tokens * self.input_rate) +
            (output_tokens * self.output_rate) +
            (cache_write * self.cache_write_rate) +
            (cache_read * self.cache_read_rate)
        ) / 1_000_000

        return round(cost, 5)
