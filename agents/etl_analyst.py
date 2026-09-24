import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_pick import pick_llm
from utils.etl_tools import ETLTools
from Models.schema import ETLAgentSchema
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool


#---------------------------ETL AGENT TOOLS-------------------------------------
#this decorator adds metadata #using this decorator from langchian.tools we converted function to tool
@tool 
def extract_load_tool(url:str,output_folder:str,format:str):
    """
    This tool extracts the data from the API and loads it into the derired location.
    """
    etl_tools=ETLTools()
    return etl_tools.extract_load(url,output_folder,format)

@tool
def trnasform_load_tool(input_file_path:str, output_folder:str, output_format:str,user_question: str) -> str:
    """
    This tool transforms the data from the specified file and loads it into the desired location i.e output folder.
    """

    etl_tools=ETLTools()
    top_3_rows=etl_tools.transform_load_context(input_file_path)
    llm=pick_llm("medium")

    prompt=f"""
            You are a Python Data Analyst who uses Pandas to analyze data. 
            You need to provide only the Pandas Code that will help to perform the right ETL operations on the data stored in the file : {input_file_path}
            as per the user's question. Do not provide any explanation or comments, only
            the code should be provided. The code should be in a format that can be executed 
            in a Python environment with Pandas installed. 
            Don't write anything else than Pandas Code. \n
            
            Create the Pandas Dataframe from the data stored in the file : {input_file_path} and then 
            write the code to transform and save the data at {output_folder}.
            Here's the user's question: {user_question}\n
            Here's the context of the data you will be analyzing: {top_3_rows}\n
    """

   # response=llm.invoke(prompt).content
    # Optional Cleaning
    #pandas_code = response.strip().strip('```').strip().lstrip('python').strip()
    # Execute the Pandas code

    response = llm.invoke(prompt).content

    if isinstance(response, list):
        response = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in response
        )

    pandas_code = response.strip()

    if pandas_code.startswith("```python"):
        pandas_code = pandas_code[len("```python"):].strip()
    elif pandas_code.startswith("```"):
        pandas_code = pandas_code[len("```"):].strip()

    if pandas_code.endswith("```"):
        pandas_code = pandas_code[:-3].strip()
    results = etl_tools.execute_code(pandas_code)

    return f"The data is transformed and saved at {output_folder} in {output_format} format. \n\n Pandas Code Executed: \n {pandas_code} \n\n Execution Result: \n {results}"

#toolkit
tools=[extract_load_tool,trnasform_load_tool]

llm=pick_llm("medium")
llm_bind=llm.bind_tools(tools)


#---------------------------- AGENT GRAPH------------------------------------

def llm_node(state: ETLAgentSchema):
    messages=state.messages #giving entire chat histoty
    prompt=f"""
            You are a Python Data Analyst who has access to tools that can extract and load, 
            transform and load data. You will be provided with a user's question 
            and you would need to perform the right ETL operations as per the user's question. 
            If the operation is performed then inform the user and end the coversation.
            Here's the chat history: {messages}\n
    """
    final_answer=llm_bind.invoke(prompt)

    state.messages=messages+[final_answer]
    return state

def tool_node(state:ETLAgentSchema):
    """
    This node is responsible for invoking the appropriate tool based on the user's questions and
    the context provided by the llm.
    """
    #list with tool messages
    
    tool_calls=state.messages[-1].tool_calls
    tools_results=[]
    tools_by_name={tool.name:tool for tool in tools}
    #loop over tool call
    for tool_call in tool_calls:
        #fetcging tool name by tool_by_name
        tool=tools_by_name[tool_call['name']]
        observation=tool.invoke(tool_call['args'])
        tools_results.append(ToolMessage(content=observation,tool_call_id=tool_call['id']))

    state.messages=state.messages+tools_results

    return state


#------------------Nodes and edges------------------------
etl_analyst_graph=StateGraph(ETLAgentSchema)
etl_analyst_graph.add_node("llm_node",llm_node)
etl_analyst_graph.add_node("tool_node",tool_node)

etl_analyst_graph.add_edge(START,"llm_node")

def is_tool_call(state:ETLAgentSchema):
    tool_calls=state.messages[-1].tool_calls

    if tool_calls:
        return "tool_node"
    else:
        return "end"

etl_analyst_graph.add_conditional_edges(
        "llm_node",is_tool_call,
        {
            "tool_node":"tool_node",
            "end": END
        }
    )

etl_analyst_graph.add_edge("tool_node","llm_node")

#compile the graph
etl_analyst=etl_analyst_graph.compile()
if __name__=="__main__":


    # Optional
    from IPython.display import display, Image
    img = Image(etl_analyst.get_graph().draw_mermaid_png())
    with open("etl_analyst_graph.png", "wb") as f:
        f.write(img.data)

    #response = etl_analyst.invoke(
    #    {"messages":[HumanMessage(content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder")]}
    #)

    response = etl_analyst.invoke(
   {"messages": [HumanMessage(content=r"""I want to transform the data stored in the r'C:\Users\dnyap\OneDrive\Desktop\OLA_AI_Data_Agent\data\extract\extracted_data.csv' file

    and save the transformed data in the r'C:\Users\dnyap\OneDrive\Desktop\OLA_AI_Data_Agent\data\extract' folder in the csv format.

    The transformation should filter the data to show bulbasaur pokemon only.""")]})

    print(response)

    print(repr(response))
    print(type(response))