import pandas as pd
from src.graph import app_graph

if __name__ == "__main__":
    initial_state = {
        "applicant": {
            "budget": 450000,
            "max_wait": 4.0,
            "preferred_towns": ["Woodlands", "Tampines", "Sengkang"]
        },
        "data_changed": False,
        "iteration_count": 0
    }
    
    print("==================================================")
    print("        RUNNING BTO COMPASS LANGGRAPH MVP         ")
    print("==================================================")
    
    final_state = app_graph.invoke(initial_state)
    
    print(f"\n--- Applicant Profile ---")
    print(f"Budget: SGD {initial_state['applicant']['budget']}")
    print(f"Max Wait: {initial_state['applicant']['max_wait']} years\n")
    
    print("================ TOP 3 RECOMMENDATIONS ================")
    print(pd.DataFrame(final_state["rankings"]).to_string(index=False))
    
    print("\n================ LLM EXPLANATION ================")
    print(final_state["explanation"])
