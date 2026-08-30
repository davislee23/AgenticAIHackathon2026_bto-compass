import pandas as pd
from src.graph import app_graph

if __name__ == "__main__":
    initial_state = {
        "applicant": {
            "applicant_type": "single",
            "age": 35,
            "budget": 300000,
            "max_wait": 4.0,
            "preferred_towns": ["Tampines", "Toa Payoh", "Sembawang"]
        },
        "data_changed": False,
        "iteration_count": 0
    }
    
    print("==================================================")
    print("        RUNNING BTO COMPASS LANGGRAPH MVP         ")
    print("==================================================")
    
    final_state = app_graph.invoke(initial_state)
    
    # CHANGE: Print from final_state to see the results of the loop!
    print(f"\n--- Applicant Profile (After Simulation) ---")
    print(f"Budget: SGD {final_state['applicant']['budget']}")
    print(f"Max Wait: {final_state['applicant']['max_wait']} years")
    print(f"Iterations Run: {final_state['iteration_count']}\n")
    
    print("================ TOP 3 RECOMMENDATIONS ================")
    print(pd.DataFrame(final_state["rankings"]).to_string(index=False))
    
    print("\n================ LLM EXPLANATION ================")
    print(final_state["explanation"])
