#will choose low end llm or high end llm based on the use case and to make the switch 
#so we dont have to change the code in multiple places or hard code again and again
# if low 
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file
from langchain_google_genai import ChatGoogleGenerativeAI
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_google_genai")

def pick_llm(level:str):
    '''
        picks the appropriate llm based on the level of the question.
        
        Args:
            level (str): The level of the question, either "easy","medium", or "hard".

        Returns:
            str: The name of the appropriate llm to use for the given level.
    '''

    if level.lower()=="low":
        return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
    elif level.lower()=="medium":
        #return ChatGoogleGenerativeAI(model="gemini-3.5-flash")
        return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
    elif level.lower()=="hard":
        return ChatGoogleGenerativeAI(model="gemini-3.5-pro")
    else:
        raise ValueError(f"Unsupported level:{level}")

#whenever we execute any other file which contains or imported this file, it will run this
#so we are adding this dunder method name name to avoid this and only run this when we execute this file directly
if __name__=="__main__":
    llm_obj=pick_llm("low")
    print(llm_obj.invoke("Hello, what is capital of India?"))