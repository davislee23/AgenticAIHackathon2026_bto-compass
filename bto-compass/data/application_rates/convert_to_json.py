import pandas as pd

# Load the CSV
df = pd.read_csv("application_rates_feb2026.csv")

# Convert and save as JSON format
df.to_json("application_rates_feb2026.json", orient="records", indent=4)

print("[✓] Successfully converted CSV to application_rates_feb2026.json")
