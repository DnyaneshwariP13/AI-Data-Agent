import os
import sys
import re
from langchain.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph,START,END

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))
from utils.llm_pick import pick_llm
from Models.schema import AgentSchema, JudgeSchema
from utils.database import DatabaseUtil


from typing import Any
 
def _extract_text(content: Any) -> str:
    """Normalise Gemini/Anthropic `.content` into a plain string.
     Handles: str | list[dict{'type':'text','text':...}] | list[Part]."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    chunks.append(part["text"])
            elif hasattr(part, "text") and getattr(part, "text"):
                chunks.append(part.text)
        return "".join(chunks).strip()
    return str(content).strip()

import re

def _clean_sql(sql: str) -> str:
    """Strip markdown code fences and stray commentary from LLM SQL output."""
    if not sql:
        return ""
    s = sql.strip()
    # Remove ```sql ... ``` or ``` ... ``` blocks
    s = re.sub(r"^```(?:sql)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    # If the model added prose around the SQL, take the first SELECT/WITH statement
    match = re.search(r"(?is)\b(select|with)\b.*", s)
    if match:
        s = match.group(0)
    return s.strip().rstrip(";") + ";"


#This python function will be treated as a llm node

#-------------------------- AI AGENT CODE STARTS HERE --------------------------
#Here we pass the entire state
def curate_ques(state: AgentSchema) -> AgentSchema:
    """
    Curates the user question based on the input state.

    Args:
        state (AgentSchema): The input state containing messages and context.

    Returns:
        AgentSchema: The updated state with the curated question.
    """
    user_question = state.user_question #coz this is pydantic model object and not dict, so we can access the attributes directly

    llm = pick_llm("low")
    raw = llm.invoke(f"Curate the following question: {user_question}").content
    curated = _extract_text(raw)

    if not curated:
        raise ValueError("LLM returned no curated question.")

    return {                                          # ← FIX: partial dict, not mutated state
        "curated_ques": curated,
        "messages": [HumanMessage(content=curated)],  # `add` reducer appends
    }


def prompt_query_context(state: AgentSchema) -> AgentSchema:
    """
    Generates a detailed prompt with SQL DB context based on the input state.

    Args:
        state (AgentSchema): The input state containing messages and context.

    Returns:
        AgentSchema: The updated state with the prompt query context.
    """
    curated_question = state.curated_ques

    conn_details={
    'host': os.environ['host'],
    'port': os.environ['port'],  
    'user': os.environ['user'],
    'password': os.environ['password'],
    'dbname': os.environ['database']
    }

    obj=DatabaseUtil(conn_details)

    schema_info= obj.schema_details('public') # Fetch schema details for the 'public' schema

    # Constructing the prompt query for the agent to generate the SQL query
    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.  

    STRICT RULES:
    - Use ONLY tables and columns that appear in the "Database Schema Details" section below.
    - NEVER invent table names, column names, or aliases.
    - If the user's question cannot be answered with the given schema, output exactly:
        SELECT 'Cannot answer with available schema' AS error;
    - Do not wrap the query in markdown fences.
    - Do not add any explanation, comment, or trailing prose.
    - Output the raw SQL only, terminated with a semicolon.
    - Unless the user asks for a specific count, always end with LIMIT 10.
    
    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}

    """

    return {"prompt_query_context": prompt}




def generate_sql_query(state: AgentSchema) -> AgentSchema:
    """
    Generates an SQL query based on the input state.

    Args:
        state (AgentSchema): The input state containing messages and context.

    Returns:
        AgentSchema: The updated state with the generated SQL query.
    """
    #prompt = state.prompt_query_context

    llm=pick_llm("medium") #we can change the level to "low" or "hard" based on the complexity of the question
    #response = llm.invoke(prompt).content
    raw=llm.invoke(state.prompt_query_context).content
    sql = _clean_sql(_extract_text(raw))

    return {"generated_sql_query": sql}




def is_safe_sql(state: AgentSchema) -> AgentSchema:
    """
    Determines whether the generated SQL query is safe to execute based on the input state.

    Args:
        state (AgentSchema): The input state containing messages and context.

    Returns:
        AgentSchema: The updated state with the safety status of the SQL query.
    """
    sql_query = state.generated_sql_query

    llm=pick_llm("medium") #we can change the level to "low" or "hard" based on the complexity of the question
    llm_judge=llm.with_structured_output(JudgeSchema) #we can change the level to "low" or "hard" based on the complexity of the question

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 
    'No'. Additionally, provide comments explaining your decision.
    Here's the SQL query to evaluate:
    {sql_query}"""

    verdict=llm_judge.invoke(prompt).model_dump() #get structured output as dict

    answer = str(verdict["answer"]).strip().capitalize()
    if answer not in ("Yes", "No"):
        answer = "No"

    return {"is_safe": answer, "comments": verdict["comments"]}
    



#canceleAgentSchemad sql query node when ans to prev is NO
def canceled_sql(state: AgentSchema)-> dict:
    final = (
        "The generated SQL query was deemed unsafe to execute. "
        f"The reason provided by the judge is: {state.comments}. "
        "Therefore, the SQL query will not be executed."
    )
    return {"final_answer": final, "messages": [AIMessage(content=final)]}

'''
#Execute the SQL query node
def execute_sql(state: AgentSchema) -> AgentSchema:
    sql_query=state.generated_sql_query

    conn_details={
        'host': os.environ['host'],
        'port': os.environ['port'],  
        'user': os.environ['user'],
        'password': os.environ['password'],
        'dbname': os.environ['database']
    }

    obj=DatabaseUtil(conn_details)
    execution_result=obj.execute_sql(sql_query)
    #state.sql_query_execution_result=execution_result

    return {"sql_query_execution_result": execution_result}'''

import json   # put this at the top of the file, with the other imports

def execute_sql(state: AgentSchema) -> dict:
    sql_query = state.generated_sql_query

    conn_details = {
        "host": os.environ["host"],
        "port": os.environ["port"],
        "user": os.environ["user"],
        "password": os.environ["password"],
        "dbname": os.environ["database"],
    }

    obj = DatabaseUtil(conn_details)
    execution_result = obj.execute_sql(sql_query)

    # Normalise to a JSON string — matches the `str` type in AgentSchema
    if execution_result is None:
        execution_result = []
    try:
        result_str = json.dumps(execution_result, default=str, indent=2)
    except Exception as e:
        result_str = json.dumps({"error": f"serialization failed: {e}"})

    return {"sql_query_execution_result": result_str}


#representation node
def represent_final_answer(state:AgentSchema)->AgentSchema:
    execution_result=state.sql_query_execution_result
    curated_question=state.curated_ques

    llm=pick_llm("low")

    prompt=f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """
    raw = llm.invoke(prompt).content
    answer = _extract_text(raw)                      

    return {"final_answer": answer, "messages": [AIMessage(content=answer)]}



#-----------------------------------Graph Building--------------------------------------

#inititate graph with this particular state
sql_agent_graph=StateGraph(AgentSchema)

#Nodes
#initiate object for each function
sql_agent_graph.add_node(curate_ques,name="curate_ques")
sql_agent_graph.add_node(prompt_query_context,name="prompt_query_context")
sql_agent_graph.add_node(generate_sql_query,name="generate_sql_query")
sql_agent_graph.add_node(is_safe_sql,name="is_safe_sql")
sql_agent_graph.add_node(canceled_sql,name="canceled_sql")
sql_agent_graph.add_node(execute_sql,name="execute_sql")
sql_agent_graph.add_node(represent_final_answer,name="represent_final_answer")
# these are the individual nodes which are not connected
#we connect each node one by one , through edge

sql_agent_graph.add_edge(START,"curate_ques")
sql_agent_graph.add_edge("curate_ques","prompt_query_context")
sql_agent_graph.add_edge("prompt_query_context","generate_sql_query")
sql_agent_graph.add_edge("generate_sql_query","is_safe_sql")


#conditional edge function
def is_safe_sql_edge(state: AgentSchema)->str:
    is_safe = state.is_safe            # ← FIX: was `is_safe_sql_response` (nonexistent)

    if str(is_safe).strip().lower() == "yes":
        return "execute_sql"
    return "canceled_sql"


sql_agent_graph.add_conditional_edges(
    "is_safe_sql",
    is_safe_sql_edge,
    {"execute_sql": "execute_sql", "canceled_sql": "canceled_sql"},
)

# Path for unsafe SQL
sql_agent_graph.add_edge("canceled_sql", END)

# Path for safe SQL: execute -> represent -> end
sql_agent_graph.add_edge("execute_sql", "represent_final_answer")  
sql_agent_graph.add_edge("represent_final_answer", END)


#compile the graph
sql_analyst= sql_agent_graph.compile()


if __name__=="__main__":
    #optional visualization
    #visualizing the graph- IPython.display import display, Image, 
    from IPython.display import display, Image
    img=Image(sql_analyst.get_graph().draw_mermaid_png)
    with open("sql_analyst_graph.png","wb") as f:
        f.write(img.data())

    # we cant send this to pydantic directly, need to send as a pydantic model
    input_schema={
        "messages": [],
        "user_question": "What are the different types of Payment Methods we have in our database",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }


    #execute the graph
    #sql_analyst_response = sql_analyst.invoke(input_schema)
    #print(sql_analyst_response["final_answer"])
    #print("messages:", sql_analyst_response["messages"])

     # Execute the Graph
    sql_analyst_response = sql_analyst.invoke(input_schema)
    print("=== MESSAGES ===")
    for m in sql_analyst_response["messages"]:
        print(f"[{type(m).__name__}] {m.content}\n")

    print("=== GENERATED SQL ===")
    print(sql_analyst_response["generated_sql_query"])
    print()

    print("=== RAW DB RESULT ===")
    print(sql_analyst_response["sql_query_execution_result"])
    print()

    print("=== FINAL ANSWER ===")
    print(sql_analyst_response["final_answer"])            # ← the human-readable answer 

