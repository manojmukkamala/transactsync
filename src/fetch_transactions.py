import re
import json
from llama_index.llms.ollama import Ollama
from typing import Optional, Tuple

class TransactionHandler:

    def __init__(self, model="qwen3:8b", request_timeout=300.0, json_mode=False, model_host="http://localhost:11434"):
        self.model = model
        self.request_timeout = request_timeout
        self.json_mode = json_mode
        self.model_host = model_host  # Corrected variable name from madel_host to model_host
        self.llm_bridge = Ollama(base_url=self.model_host, model=self.model, request_timeout=self.request_timeout, json_mode=self.json_mode)
    
    def get_transaction(self, e_mail: dict, llm_prompt: Optional[str] = None) -> Tuple[str, dict]:
        """
        Extract transaction details from an email using a language model.

        Args:
            e_mail (dict): A dictionary containing the email's subject, date, sender, recipient, and body.
            llm_prompt (Optional[str]): An optional custom prompt to use with the language model.

        Returns:
            Tuple[str, dict]: A tuple containing the reasoning text and the parsed JSON object.
        
        Raises:
            ValueError: If no JSON is found or JSON parsing fails.    
        """

        if llm_prompt is None:
            llm_prompt = f"""
            extract the following fields from this email:
            ```
            - account name or account number or card number or last 4 #
            - transaction date
            - transaction amount
            - merchant (if available)
            ```

            and return JSON with the following keys and data types: 
            ```
            - account string
            - transaction_amount float
            - transaction_date timestamp
            - merchant string
            - transaction_flag true if it is a transaction else false
            ```       
            """ 
        llm_prompt = llm_prompt + f"""
            \n from_address: {e_mail["from_address"]}
            \n date: {e_mail["email_date"]}
            \n subject: {e_mail["subject"]}
            \n body: \n{e_mail["body"].strip()}
            """.strip() 

        llm_response = self.llm_bridge.complete(llm_prompt).text.strip()

        llm_reasoning, llm_prediction = self.parse_model_output(llm_response)

        return llm_reasoning, llm_prediction


    @staticmethod
    def parse_model_output(raw_output: str, schema_class: Optional[type] = None) -> Tuple[str, dict]:
        """
        Parse the raw output from a language model to extract reasoning text and structured data.

        Args:
            raw_output (str): The raw output string from the language model.
            schema_class (Optional[type]): A Pydantic class to validate/parse the extracted JSON.

        Returns:
            Tuple[str, dict]: A tuple containing the reasoning text and the parsed JSON object.

        Raises:
            ValueError: If no JSON is found or JSON parsing fails.
        """
        # Match from the first '{' to the last '}' (greedy) — fallback if not recursive
        json_match = re.search(r"\{(?:.|\n)*?\}", raw_output)
        
        if not json_match:
            raise ValueError("No JSON object found in model output.")

        json_str = json_match.group(0)
        reasoning_text = raw_output[:json_match.start()].strip()

        try:
            parsed = json.loads(json_str)
            if schema_class:
                parsed = schema_class(**parsed)
            return reasoning_text, parsed
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}\nExtracted: {json_str}")
