from openai import OpenAI
from sentence_transformers import SentenceTransformer
from transformers import AutoProcessor, ClapModel, CLIPProcessor, CLIPModel, pipeline
import torch
from torchvision import transforms

import config_tdb


class ModelRepository:
    def __init__(self):
        self.models = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device_id = torch.cuda.current_device() if torch.cuda.is_available() else -1

    def get_text_model(self):
        if 'text' not in self.models:
            if config_tdb.USE_BART:
                self.models['text'] = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=self.device_id)
            else:
                self.models['text'] = SentenceTransformer('all-MiniLM-L6-v2')
        return self.models['text']

    def get_image_model(self):
        if 'image' not in self.models:
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            if self.device_id >= 0:
                model = model.to(self.device_id)
            preprocess = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            t = transforms.Compose([transforms.ToPILImage()])
            self.models['image'] = (model, preprocess, t) 
        return self.models['image']

    def get_audio_model(self):
        if 'audio' not in self.models:
            model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
            if self.device_id >= 0:
                model = model.to(self.device_id)
            preprocess = AutoProcessor.from_pretrained("laion/clap-htsat-unfused")
            self.models['audio'] = (model, preprocess)
        return self.models['audio']
    
    def get_gpt_model(self):
        if 'image' not in self.models:
            self.models['image'] = OpenAI()
        return self.models['image']
