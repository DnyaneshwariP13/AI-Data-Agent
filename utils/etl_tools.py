# here we have all helper function which are nothing but tools
import os
import sys
import requests
import pandas as pd

class ETLTools:
    def __init__(self):
        pass

    def extract_load(self,url:str,output_folder:str,format:str):
        #here we are fetching data from api, we can add more
        """
        This tool extracts data from the API(URL) and loads it into the 
        desired location (destination).

        Args:
            url(str): The API endpoint from which to extract data.
            output_folder(str): The folder where the extracted data will be saved.

        Returns:
            str: A message indicating the success or failure of the operation.
        """
        #trying to write in output folder from root dir
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        output_folder= os.path.join(project_root,output_folder)

        #fetch the data
        #we are using pokemon api here we get lot of pokemons and names etc

        try:
            response=requests.get(url)
            response.raise_for_status()
            data=response.json()    

            filename=os.path.join(output_folder,f"extracted_data.{format}")
            os.makedirs(output_folder,exist_ok=True)

            df=pd.json_normalize(data)
            if format=='csv':
                df.to_csv(filename,index=False)
            elif format=='json':
                df.to_json(filename,orient="records",lines=True)
            elif format=='parquet':
                df.to_json(filename,index=False)
            else:
                return f"Unsupported format: {format}"

            return f"Data successfully extracted and saved to {filename}"

        except requests.exceptions.RequestExceptionException as e:
            return f"Failed to extract data: {e}"

    def transform_load_context(self,file_path:str):
        """
        This tool transfroms the data from the specified file and loads it into the desierd location(output_folder).

        """
        file_extension=os.path.splitext(file_path)[1].lower()
        if file_extension==".csv":
            df=pd.read_csv(file_path)
        elif file_extension==".json":
            df=pd.read_json(file_path,lines=True)
        elif file_extension==".parquet":
            df=pd.read_parquet(file_path)
        else:
            return f"Unsupported file format: {format}"
        top_3_rows=str(df.head(3))

        return top_3_rows

    def execute_code(self,code:str):
        try:
            exec(code)
            return "Code executed succesfully!"
        except Exception as e: 
            return f"Failed to execute code: {e}"
        
if __name__=="__main__":
        
    obj=ETLTools()
    #obj.extract_load("https://pokeapi.co/api/v2/pokemon/","data/extract","csv")
    path=r"C:\Users\dnyap\OneDrive\Desktop\OLA_AI_Data_Agent\data\extract\extracted_data.csv"
    print(obj.transform_load_context(path))




