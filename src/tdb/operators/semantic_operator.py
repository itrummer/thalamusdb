'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
import base64
import json

from tdb.execution.counters import LLMCounters, TdbCounters
from pathlib import Path


class SemanticOperator:
    """ Base class for semantic operators. """
    
    def __init__(self, db, operator_ID, batch_size):
        """
        Initializes the semantic operator with a unique identifier.
        
        The unique operator identifier is used to create a temporary
        table in the database to store the results of the operator.
        
        Args:
            db: Represents the source database.
            operator_ID (str): Unique identifier for the operator.
            batch_size (int): Determines number of items to process per call.
        """
        self.db = db
        self.operator_ID = operator_ID
        self.batch_size = batch_size
        self.counters = TdbCounters()
        src_path = Path(__file__).parent.parent.parent.parent
        model_path = src_path / 'config' / 'models.json'
        if not model_path.exists():
            # Use default settings
            self.models = {
                "models":[
                    {
                        "id": "gpt-4o", 
                        "modalities":["text", "image"], 
                        "priority": 10},
                    {
                        "id": "gpt-4o-audio-preview", 
                        "modalities":["text", "audio"], 
                        "priority": 10}
                ]
            }
            # raise FileNotFoundError(
            #     f'Model configuration file not found at {model_path}')
        else:
            with open(model_path) as file:
                # Load model configuration from JSON file
                self.models = json.load(file)
                # print(self.models)

    def _encode_item(self, item_text):
        """ Encodes an item as message for LLM processing.
        
        Args:
            item_text (str): Text of the item to encode, can be a path.
        
        Returns:
            dict: Encoded item as a dictionary with 'role' and 'content'.
        """
        file_path = Path(item_text)
        if not file_path.is_absolute():
            file_path = Path(self.db.db_path).parent / file_path
        if any(
            item_text.endswith(extension) \
            for extension in ['.png', '.jpg', '.jpeg']):
            with file_path.open('rb') as image_file:
                image = base64.b64encode(
                    image_file.read()).decode('utf-8')
                
            return {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{image}',
                    'detail': 'low'
                    }
                }
        elif any(
            item_text.endswith(extension) \
            for extension in ['.wav', '.mp3']):
            with file_path.open('rb') as audio_file:
                audio = base64.b64encode(
                    audio_file.read()).decode('utf-8')
            
            audio_format = item_text.split('.')[-1]
            return {
                'type': 'input_audio',
                'input_audio' : {
                    'data': audio,
                    'format': audio_format}
                }
        else:
            return {
                'type': 'text',
                'text': item_text
            }
    
    def _select_model(self, messages):
        """ Selects the LLM model based on content types of messages.
        
        Args:
            messages (list): List of messages to send to the model.
        
        Returns:
            str: The selected model name.
        """
        # Collect data types in messages (audio, text, image)
        data_types = set()
        for message in messages:
            for content_part in message['content']:
                match content_part['type']:
                    case 'text':
                        data_types.add('text')
                    case 'image_url':
                        data_types.add('image')
                    case 'input_audio':
                        data_types.add('audio')
                    case _:
                        raise ValueError(
                            'Unknown message type: ' 
                            f'{message["type"]}!')
                    
        # Select model based on data types
        eligible_models = []
        for model in self.models['models']:
            if all(data_type in model['modalities'] \
                   for data_type in data_types):
                eligible_models.append(model)
        
        # Sort models by priority (descending) and return name of first
        if not eligible_models:
            raise ValueError(
                'No eligible models found for ' 
                f'the given data types ({data_types})!')
        eligible_models.sort(key=lambda x: x['priority'], reverse=True)
        return eligible_models[0]['id']
    
    def _gpt4_style_model(self, model):
        """ Checks if the model uses the GPT-4 tokenizer and token limits.
        
        Args:
            model (str): Name of the model to check.
        
        Returns:
            bool: can use the same arguments for completions as for GPT-4?
        """
        return 'gpt-4' in model or 'gpt-3.5' in model
    
    def execute(self, order):
        """ Execute operator on a data batch.
        
        Args:
            order (tuple): None or tuple with column name and "ascending" flag.            
        """
        raise NotImplementedError()
    
    def prepare(self):
        """ Prepare for execution by creating the temporary table. """
        raise NotImplementedError()
    
    def update_cost_counters(self, model, llm_reply):
        """ Update cost-related counters from LLM reply.
        
        Args:
            model (str): Name of the model used for the LLM call.
            llm_reply: The reply from the LLM (currently only OpenAI).
        """
        if model not in self.counters.model2counters:
            self.counters.model2counters[model] = LLMCounters()
        
        llm_counters = self.counters.model2counters[model]
        llm_counters.LLM_calls += 1
        llm_counters.input_tokens += llm_reply.usage.prompt_tokens
        for field in ["text", "image", "audio"]:
            added_tokens = getattr(llm_reply.usage.prompt_tokens_details, f"{field}_tokens", None)
            if added_tokens is not None:
                setattr(llm_counters, f"{field}_input_tokens",
                        getattr(llm_counters, f"{field}_input_tokens") + added_tokens)
        llm_counters.output_tokens += llm_reply.usage.completion_tokens