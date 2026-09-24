from agents.data_agent import data_agent
from langchain_core.messages import HumanMessage
from agents.data_agent import data_agent
from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst
if __name__ == "__main__":
    response = data_agent.invoke(
        {"messages":[HumanMessage(content="How many payments are thrugh credit cards which are done after 12AM")],
         "route_response": ""}
    )

    print(response)