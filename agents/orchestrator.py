from langgraph.graph import StateGraph, END
from .graph_state import AgentState
from . import graph_nodes as nodes
from . import graph_edges as edges

# Define the graph
workflow = StateGraph(AgentState)

# Add all the nodes
workflow.add_node("diagnosis_node", nodes.diagnosis_node)
workflow.add_node("ueba_check_node", nodes.ueba_check_node)
workflow.add_node("customer_engagement_node", nodes.customer_engagement_node)
workflow.add_node("rca_insights_node", nodes.rca_insights_node)

# Set the entry point
workflow.set_entry_point("diagnosis_node")

# Add conditional edges
workflow.add_conditional_edges(
    "diagnosis_node",
    edges.should_engage,
    {
        "ueba_check_node": "ueba_check_node",
        "end": END
    }
)

workflow.add_conditional_edges(
    "ueba_check_node",
    edges.is_allowed,
    {
        "customer_engagement_node": "customer_engagement_node",
        "end": END
    }
)

# Add normal edges
workflow.add_edge("customer_engagement_node", "rca_insights_node")
workflow.add_edge("rca_insights_node", END)

# Compile the graph into a runnable app
app = workflow.compile()

# --- Helper function to run the graph ---
def run_graph(telemetry_tick: dict):
    """
    Invokes the compiled LangGraph app with the initial state.
    """
    inputs = {
        "vin": telemetry_tick.get('vin'),
        "telemetry_data": telemetry_tick
    }
    
    # The 'app.invoke()' call will run the graph from start to finish
    # for this single telemetry tick.
    try:
        app.invoke(inputs)
    except Exception as e:
        print(f"Error invoking graph for VIN {inputs['vin']}: {e}")