from enum import Enum


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
    

class ImageDataset():
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