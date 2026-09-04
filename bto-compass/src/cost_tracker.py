class UsageTracker:
    PRICING = {
        # Claude Haiku 4.5
        "us.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.00, "output": 5.00},
        "anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.00, "output": 5.00},
        
        # Groq Models
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        
        # Fallback
        "default": {"input": 1.00, "output": 5.00}
    }

    def calculate_cost(self, usage: dict, model_id: str = "default") -> float:
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
        
        rates = self.PRICING.get(model_id, self.PRICING["default"])
        
        input_cost = (input_tokens / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        
        return input_cost + output_cost
