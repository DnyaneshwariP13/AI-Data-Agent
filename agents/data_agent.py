import os
import sys
import re
from langchain.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph,START,END

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))
from utils.llm_pick import pick_llm
from Models.schema import AgentSchema, JudgeSchema, RouterSchema, DataAgentSchema
from utils.database import DatabaseUtil

from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst

llm=pick_llm("medium")
#should generate only literal value provided
llm_router=llm.with_structured_output(RouterSchema)

#----------------------------- Data Agent Graph ---------------------------------------

def router_node(state:DataAgentSchema):
    #to get last human message
    message=state.messages[-1].content
    #model dump returns dict
    route_response_dict=llm_router.invoke(message).model_dump()
    route_response= route_response_dict['answer']
    print("######################################3")
    print(route_response)
    state.route_response=route_response
    return state

def etl_node(state:DataAgentSchema):
    message=state.messages[-1].content
    response=etl_analyst.invoke(

        {"messages":[HumanMessage(content=f"""{message}""")]}
    )
    state.messages=state.messages+[response]
    return state

def sql_node(state:DataAgentSchema):
    message=state.messages[-1].content

    input_schema = {
        "messages": [],
        "user_question": f"{message}",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }  

    response=sql_analyst.invoke(input_schema)
    state.messages=state.messages+[response]
    return state

data_agent_graph=StateGraph(DataAgentSchema)
data_agent_graph.add_node("router_node",router_node)
data_agent_graph.add_node("etl_node",etl_node)
data_agent_graph.add_node("sql_node",sql_node)

data_agent_graph.add_edge(START,"router_node")

def route_edge(state: DataAgentSchema) -> str:
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


data_agent_graph.add_conditional_edges("router_node", route_edge,
                                      {
                                          "sql_node": "sql_node",
                                          "etl_node": "etl_node"
                                      })

data_agent = data_agent_graph.compile()

# Optional|
from IPython.display import display, Image
img = Image(data_agent.get_graph().draw_mermaid_png())
with open("data_agent_graph.png", "wb") as f:
    f.write(img.data)


if __name__=="__main__":
    response = data_agent.invoke(
        {"messages":[HumanMessage(content="I want to to know how many drivers are there and riders are there")],
         "route_response": ""}
    )

    print(response)
