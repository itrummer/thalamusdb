from enum import Enum
import os
from pathlib import Path

import cv2
import librosa
import numpy as np
from torch.utils.data import Dataset


class DataType(Enum):
    NUM, TEXT, IMG, AUDIO = range(4)

    @classmethod
    def is_unstructured_except_text(cls, datatype):
        if datatype is DataType.NUM or datatype is DataType.TEXT:
            return False
        return True

    @classmethod
    def is_unstructured(cls, datatype):
        if datatype is DataType.NUM:
            return False
        return True
    

class AudioDataset(Dataset):
    def __init__(self, valid_idxs=None, name='AudioCaps'):
        """
        Load audio clip's waveform.
        Args:
            name: 'AudioCaps', 'Clotho
        """
        super(AudioDataset, self).__init__()
        self.name = name
        audio_dir_prefix = f'{name.lower()}/waveforms'
        audio_dirs = [f'{audio_dir_prefix}/train/', f'{audio_dir_prefix}/test/', f'{audio_dir_prefix}/val/']
        self.audio_paths = [os.path.join(audio_dir, f) for audio_dir in audio_dirs for f in os.listdir(audio_dir)]
        self.audio_names = [Path(audio_path).stem for audio_path in self.audio_paths]
        if valid_idxs is not None:
            self.audio_paths = [self.audio_paths[idx] for idx in valid_idxs]
            self.audio_names = [self.audio_names[idx] for idx in valid_idxs]

    def __len__(self):
        return len(self.audio_names)

    def __getitem__(self, idx):
        audio_name = self.audio_names[idx]
        audio_path = self.audio_paths[idx]
        audio, _ = librosa.load(self.audio_paths[idx], sr=32000, mono=True)
        audio = AudioDataset.pad_or_truncate(audio, 32000 * 10)
        return audio, audio_name, audio_path, idx, len(audio)

    @staticmethod
    def pad_or_truncate(audio, audio_length):
        """Pad all audio to specific length."""
        length = len(audio)
        if length <= audio_length:
            return np.concatenate((audio, np.zeros(audio_length - length)), axis=0)
        else:
            return audio[:audio_length]


class ImageDataset(Dataset):
    """Image dataset."""

    def __init__(self, img_paths, transform=None):
        """
        Args:
            img_paths (string): List of paths to all images.
            transform (callable, optional): Optional transform to be applied on a sample.
        """
        self.img_paths = img_paths
        self.transform = transform

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, idx):
        img_path = self.img_paths[idx]
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.transform:
            img = self.transform(img)

        return img, None


