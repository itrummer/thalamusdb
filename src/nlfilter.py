import base64

import torch
import numpy as np
import matplotlib.pyplot as plt
from sentence_transformers import util
import playsound
import streamlit as st

import config_tdb
from datatype import DataType


class SimilarityProcessor:
    """Superclass for processor that computes similarity scores."""

    def __init__(self, dataset, model, device):
        self.dataset = dataset
        self.nr_total = len(self.dataset)
        self.model = model
        self.device = device
        # self.processed_idxs = set()

    def get_item(self, idx):
        pass

    def show(self, idx):
        pass

    def compute_scores(self, ordered_idxs, percent):
        pass


class AudioProcessor(SimilarityProcessor):
    def __init__(self, dataset, model, preprocess, device):
        super().__init__(dataset, model, device)
        self.preprocess = preprocess
        self.idx_to_embedding = dict()
        self.text_to_embedding = dict()

    def get_item(self, idx):
        _, _, audio_path, *_ = self.dataset[idx]
        return audio_path

    def show(self, idx):
        audio_path = self.get_item(idx)
        playsound.playsound(audio_path)

    def compute_scores(self, text, idxs_to_process):
        """Process new audios and return a mapping from audio index to score.
        Iterate based on the given input indexes."""
        idx_to_score = {}
        for idx in idxs_to_process:
            embedding = self.idx_to_embedding.get(idx)
            text_embedding = self.text_to_embedding.get(text)
            if embedding is None or text_embedding is None:
                audio, *_ = self.dataset[idx]
                with torch.no_grad():
                    input_text = [text]
                    inputs = self.preprocess(
                        text=input_text,
                        audios=audio,
                        sampling_rate=48000,
                        return_tensors="pt",
                        padding=True,
                    )
                    if self.device >= 0:
                        inputs = inputs.to(self.device)
                    outputs = self.model(**inputs)
                    embedding = outputs.audio_embeds
                    text_embedding = outputs.text_embeds
                    # print(embedding.shape)
                    # print(embedding)
                    # print(text_embedding.shape)
                    # print(text_embedding)
                    # print(outputs.logits_per_audio)
                    # print(outputs.logits_per_text)
                    # embedding, text_embedding = self.model(audio, text)
                if idx not in self.idx_to_embedding:
                    self.idx_to_embedding[idx] = embedding
                if text not in self.text_to_embedding:
                    self.text_to_embedding[text] = text_embedding
            idx_to_score[idx] = 100.0 * util.cos_sim(embedding, text_embedding).item()
            # print(util.cos_sim(embedding, text_embedding))
        return idx_to_score


class ImageProcessor(SimilarityProcessor):
    def __init__(self, dataset, model, preprocess, device):
        super().__init__(dataset, model, device)
        self.preprocess = preprocess
        self.idx_to_embedding = dict()
        self.text_to_embedding = dict()

    def get_item(self, idx):
        img, _ = self.dataset[idx]
        return img

    def show(self, idx):
        img = self.get_item(idx)
        plt.imshow(img)
        plt.show()

    def compute_scores(self, text, idxs_to_process):
        """Process new images and return a mapping from image index to score.
        Iterate based on the given input indexes."""
        idx_to_score = {}
        for idx in idxs_to_process:
            embedding = self.idx_to_embedding.get(idx)
            text_embedding = self.text_to_embedding.get(text)
            if embedding is None or text_embedding is None:
                img, _ = self.dataset[idx]
                with torch.no_grad():
                    input_text = [text]
                    inputs = self.preprocess(
                        text=input_text,
                        images=img,
                        return_tensors="pt",
                        padding=True,
                    )
                    if self.device >= 0:
                        inputs = inputs.to(self.device)
                    outputs = self.model(**inputs)
                    embedding = outputs.image_embeds
                    text_embedding = outputs.text_embeds
                if idx not in self.idx_to_embedding:
                    self.idx_to_embedding[idx] = embedding
                if text not in self.text_to_embedding:
                    self.text_to_embedding[text] = text_embedding
            idx_to_score[idx] = 100.0 * util.cos_sim(embedding, text_embedding).item()
            # print(util.cos_sim(embedding, text_embedding))
        return idx_to_score


class GPTImageProcessor(SimilarityProcessor):
    def __init__(self, dataset, model):
        super().__init__(dataset, model, None)
        self.text2idx2result = dict()
        if config_tdb.GUI:
            self.progress_bar = None

    def get_item(self, idx):
        img, _ = self.dataset[idx]
        return img

    def show(self, idx):
        img = self.get_item(idx)
        plt.imshow(img)
        plt.show()

    def encode_image(self, idx):
        img_path = self.dataset.img_paths[idx]
        with open(img_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def compute_scores(self, text, idxs_to_process):
        """Process new images and return a mapping from image index to score.
        Iterate based on the given input indexes."""
        if config_tdb.GUI:
            display_item = st.empty()
        if text not in self.text2idx2result:
            self.text2idx2result[text] = {}
        idx_to_score = {}
        for idx in idxs_to_process:
            if config_tdb.GUI:
                item = self.dataset[idx][0]
                with display_item.container():
                    st.write(f"Image Item Being Processed (See Below):")
                    st.image(item)
                if self.progress_bar:
                    self.progress_bar.progress(
                        st.session_state["nr_requests"]
                        / st.session_state["total_nr_requests"],
                        text=st.session_state["progress_text"],
                    )
                    if (
                        st.session_state["nr_requests"]
                        < st.session_state["total_nr_requests"] - 1
                    ):
                        st.session_state["nr_requests"] += 1
            if idx in self.text2idx2result[text]:
                idx_to_score[idx] = self.text2idx2result[text][idx]
            else:
                prompt = f'Does the following text describe the image? "{text}"\nAnswer 1 for Yes, 0 for No.\n'
                base64_img = self.encode_image(idx)
                response = self.model.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_img}",
                                        "detail": "low",
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "\nAnswer: ",
                                },
                            ],
                        }
                    ],
                    max_tokens=1,
                    logit_bias={15: 100, 16: 100},
                )
                print(response)
                result = int(response.choices[0].message.content)
                idx_to_score[idx] = result
                self.text2idx2result[text][idx] = result
        if config_tdb.GUI:
            display_item.empty()
        return idx_to_score


class GPTTextProcessor(SimilarityProcessor):
    def __init__(self, dataset, model):
        super().__init__(dataset, model, None)
        self.text2idx2result = dict()
        if config_tdb.GUI:
            self.progress_bar = None

    def get_item(self, idx):
        txt = self.dataset[idx]
        return txt

    def show(self, idx):
        txt = self.get_item(idx)
        print(txt)

    def compute_scores(self, text, idxs_to_process):
        """Process new text and return a mapping from text index to score.
        Iterate based on the given input indexes."""
        if config_tdb.GUI:
            display_item = st.empty()
        if text not in self.text2idx2result:
            self.text2idx2result[text] = {}
        idx_to_score = {}
        for idx in idxs_to_process:
            item = self.dataset[idx]
            if config_tdb.GUI:
                with display_item.container():
                    st.write(f"Text Item Being Processed (See Below):")
                    st.write(item)
                if self.progress_bar:
                    self.progress_bar.progress(
                        st.session_state["nr_requests"]
                        / st.session_state["total_nr_requests"],
                        text=st.session_state["progress_text"],
                    )
                    if (
                        st.session_state["nr_requests"]
                        < st.session_state["total_nr_requests"] - 1
                    ):
                        st.session_state["nr_requests"] += 1
            if idx in self.text2idx2result[text]:
                idx_to_score[idx] = self.text2idx2result[text][idx]
            else:
                prompt = f'Does the following description match the given text? \nDescription: "{text}"\nText: {item}\nEnter 1 for Yes or 0 for No.\nAnswer: '
                response = self.model.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt,
                                },
                                {
                                    "type": "text",
                                    "text": "\nAnswer: ",
                                },
                            ],
                        }
                    ],
                    max_tokens=1,
                    logit_bias={15: 100, 16: 100},
                )
                print(response)
                result = int(response.choices[0].message.content)
                idx_to_score[idx] = result
                self.text2idx2result[text][idx] = result
        if config_tdb.GUI:
            display_item.empty()
        return idx_to_score


class TextProcessor(SimilarityProcessor):
    def __init__(self, dataset, model, device):
        super().__init__(dataset, model, device)
        self.idx_to_embedding = dict()
        # Indirectly check if BART model.
        if hasattr(model, "model"):
            self.compute_scores = self._compute_scores_bart
        else:
            self.compute_scores = self._compute_scores

    def get_item(self, idx):
        txt = self.dataset[idx]
        return txt

    def show(self, idx):
        txt = self.get_item(idx)
        print(txt)

    def _compute_scores(self, text, idxs_to_process):
        """Process new text and return a mapping from text index to score.
        Iterate based on the given input indexes."""
        if not idxs_to_process:
            return dict()
        text_embedding = self.model.encode(text, convert_to_tensor=True).to(self.device)
        # Split indexes based on cache.
        idxs_cache = [idx for idx in idxs_to_process if idx in self.idx_to_embedding]
        idxs_no_cache = [
            idx for idx in idxs_to_process if idx not in self.idx_to_embedding
        ]
        # Get or compute embeddings.
        if idxs_no_cache:
            txts = [self.dataset[idx] for idx in idxs_no_cache]
            embeddings_no_cache = self.model.encode(txts, convert_to_tensor=True).to(
                self.device
            )
            for idx, embedding in zip(
                idxs_no_cache, embeddings_no_cache.detach().cpu().numpy()
            ):
                self.idx_to_embedding[idx] = embedding
        if idxs_cache:
            embeddings_cache = torch.from_numpy(
                np.vstack([self.idx_to_embedding[idx] for idx in idxs_cache])
            ).to(self.device)
        embeddings = (
            embeddings_no_cache
            if not idxs_cache
            else (
                embeddings_cache
                if not idxs_no_cache
                else torch.vstack((embeddings_cache, embeddings_no_cache))
            )
        )
        # Compute scores.
        scores = (
            util.cos_sim(text_embedding, embeddings).flatten().detach().cpu().tolist()
        )
        idxs_to_process = idxs_cache + idxs_no_cache
        idx_to_score = dict(zip(idxs_to_process, scores))
        return idx_to_score

    def _compute_scores_bart(self, text, idxs_to_process):
        """Bart model requires a different implementation."""
        if not idxs_to_process:
            return dict()
        candidate_labels = [text]

        idx_to_score = {}
        for idx in idxs_to_process:
            txt = self.dataset[idx]
            if txt.strip():
                result = self.model(txt, candidate_labels, multi_label=True)
                idx_to_score[idx] = result["scores"][0]
            else:
                idx_to_score[idx] = 0  # Valid for BART.
        return idx_to_score


class FilterResultNrs:
    def __init__(self, nr_true, nr_false, nr_unsure, nr_total, ordering_to_cnt):
        self.t = nr_true
        self.f = nr_false
        self.u = nr_unsure
        self.nr_total = nr_total
        self.ordering_to_cnt = ordering_to_cnt

    @property
    def processed(self):
        return self.t + self.f + self.u

    @staticmethod
    def laplace_smoothing(nr_true, nr_false, nr_unsure):
        alpha = 1
        nr_total = nr_true + nr_false + nr_unsure
        nr_true = nr_total * (nr_true + alpha) / (nr_total + 3 * alpha)
        nr_false = nr_total * (nr_false + alpha) / (nr_total + 3 * alpha)
        nr_unsure = nr_total * (nr_unsure + alpha) / (nr_total + 3 * alpha)
        return nr_true, nr_false, nr_unsure

    def corner_case(self, ordering):
        one_plus_p = self.nr_total / self.processed
        # print(f'Reached all data so processing remainder instead: {1 - (1 / one_plus_p)} {self.processed} {self.nr_total}.')
        nr_true = self.t * one_plus_p
        nr_false = self.f * one_plus_p
        nr_unsure = self.nr_total - nr_true - nr_false

        # Laplace smoothing.
        if config_tdb.GUI:
            nr_true, nr_false, _ = FilterResultNrs.laplace_smoothing(nr_true, nr_false, nr_unsure)
            nr_unsure = self.nr_total - nr_true - nr_false
        
        nr_newly_processed = self.nr_total - self.processed
        ordering_to_cnt = self.ordering_to_cnt.copy()
        ordering_to_cnt[ordering] = (
            ordering_to_cnt.get(ordering, 0) + nr_newly_processed
        )
        return FilterResultNrs(
            nr_true, nr_false, nr_unsure, self.nr_total, ordering_to_cnt
        )

    def estimate(self, percent, ordering=("uniform",)):
        nr_newly_processed = self.nr_total * percent
        ratio = (nr_newly_processed + self.processed) / self.processed
        nr_true = self.t * ratio
        nr_false = self.f * ratio
        nr_unsure = self.u * ratio
        
        # Laplace smoothing.
        if config_tdb.GUI:
            nr_true, nr_false, nr_unsure = FilterResultNrs.laplace_smoothing(nr_true, nr_false, nr_unsure)
        
        if nr_true + nr_false + nr_unsure > self.nr_total:
            return self.corner_case(ordering)
        else:
            ordering_to_cnt = self.ordering_to_cnt.copy()
            ordering_to_cnt[ordering] = (
                ordering_to_cnt.get(ordering, 0) + nr_newly_processed
            )
            return FilterResultNrs(
                nr_true, nr_false, nr_unsure, self.nr_total, ordering_to_cnt
            )


class FilterResult:
    def __init__(self, idxs_t, idxs_f, idxs_u, nr_total, ordering_to_cnt):
        self.t = idxs_t
        self.f = idxs_f
        self.u = idxs_u
        self.nr_total = nr_total
        self.ordering_to_cnt = ordering_to_cnt

    def nrs(self):
        return FilterResultNrs(
            len(self.t), len(self.f), len(self.u), self.nr_total, self.ordering_to_cnt
        )


class NLFilter:
    """Processor should handle all type-specific operations while the filter is invariant."""

    def __init__(self, col, text):
        self.col = col
        self.text = text
        # Lower and upper thresholds.
        self._lower = 0.1 if config_tdb.GUI else None
        self._upper = 0.9 if config_tdb.GUI else None
        self._min_score = None
        self._max_score = None
        self.idx_to_score = {}
        # Default process percent.
        if config_tdb.GUI:
            self.default_process_percent = 10 / self.col.processor.nr_total
        else:
            self.default_process_percent = (
                0.001 if self.col.datatype == DataType.AUDIO else 0.01
            )  # if self.col.datatype == DataType.IMG else 0.1
        # Store information for count per ordering.
        self.ordering_to_cnt = {}

    @property
    def lower(self):
        return self._min_score - 0.001 if self._lower is None else self._lower

    @property
    def upper(self):
        return self._max_score + 0.001 if self._upper is None else self._upper

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.col.name) + " = " + str(self.text)

    def __str__(self):
        return f"NL({self.col.name}, {self.text})"

    def update(self, percent, ordering_tpl=None):
        """Update mapping of image index to score."""
        nr_total = self.col.processor.nr_total
        # Create a list of idxs to be processed.
        if ordering_tpl is None:
            ordered_idxs = range(nr_total)
            ordering = ("uniform",)
        else:
            ordered_idxs, ordering = ordering_tpl
        idxs_to_process = []
        # Could process less number of items than this.
        nr_to_process = max(int(nr_total * percent), 1)
        cnt = 0
        for idx in ordered_idxs:
            if idx not in self.idx_to_score:
                idxs_to_process.append(idx)
                cnt += 1
                if cnt == nr_to_process:
                    break
        # Compute scores and set lower and upper if initial update.
        idx_to_score_new = (
            self.col.processor.compute_scores(self.text, idxs_to_process)
            if len(idxs_to_process) > 0
            else {}
        )
        nr_newly_processed = len(idx_to_score_new)
        if nr_newly_processed == 0:
            print(
                f"No items left to process: {self.col.name} {len(self.idx_to_score)} {percent} {nr_to_process}."
            )
        else:
            self.ordering_to_cnt[ordering] = (
                self.ordering_to_cnt.get(ordering, 0) + nr_newly_processed
            )
        self.idx_to_score.update(idx_to_score_new)
        if self._lower is None:
            self._min_score = min(self.idx_to_score.values())
        if self._upper is None:
            self._max_score = max(self.idx_to_score.values())
        # print(f'NLFilter: {len(self.idx_to_score)} {sum(score >= self.upper for score in self.idx_to_score.values())} {self._lower} {self._upper} {self._min_score} {self._max_score}')
        return idx_to_score_new

    def streamlit_collect_user_feedback_get(self, weight):
        cur_score = self.lower * (1 - weight) + self.upper * weight
        unsure_items = [
            x for x in self.idx_to_score.items() if self.lower < x[1] < self.upper
        ]
        if len(unsure_items) == 0:
            print("No unsure items left. Process more items first.")
            return None
        else:
            idx, val = min(unsure_items, key=lambda x: abs(cur_score - x[1]))
        return self.col.processor.get_item(idx), idx

    def streamlit_collect_user_feedback_put(self, is_yes, idx):
        val = self.idx_to_score[idx]
        if is_yes:
            self._upper = val
        else:
            self._lower = val

    def collect_user_feedback(self, weight, ground_truth=None):
        print(f"{self.text}?")
        cur_score = self.lower * (1 - weight) + self.upper * weight
        unsure_items = [
            x for x in self.idx_to_score.items() if self.lower < x[1] < self.upper
        ]
        if len(unsure_items) == 0:
            print("No unsure items left. Process more items first.")
        else:
            idx, val = min(unsure_items, key=lambda x: abs(cur_score - x[1]))
            print(f"(Current score: {val})")
            if ground_truth is None:  # or self.col.datatype is not DataType.AUDIO:
                # For benchmarks, playing audios take too much time.
                self.col.processor.show(idx)
            if ground_truth is None:
                while True:
                    feedback = input()
                    if (
                        feedback == "t"
                        or feedback == "T"
                        or feedback == "y"
                        or feedback == "Y"
                    ):
                        self._upper = val
                        return
                    elif (
                        feedback == "f"
                        or feedback == "F"
                        or feedback == "n"
                        or feedback == "N"
                    ):
                        self._lower = val
                        return
                    elif feedback == "re":
                        self.col.processor.show(idx)
                    else:
                        print("Enter either t/T/y/Y or f/F/n/N")
            else:
                if val >= ground_truth:
                    print("Automated Feedback: TRUE")
                    self._upper = val
                else:
                    print("Automated Feedback: FALSE")
                    self._lower = val

    def true_idxs(self):
        idxs = {idx for idx, score in self.idx_to_score.items() if score >= self.upper}
        return idxs

    def false_idxs(self):
        idxs = {idx for idx, score in self.idx_to_score.items() if score <= self.lower}
        return idxs

    def unsure_idxs(self):
        idxs = {
            idx
            for idx, score in self.idx_to_score.items()
            if self.lower < score < self.upper
        }
        return idxs

    def idxs_tfu(self):
        return FilterResult(
            self.true_idxs(),
            self.false_idxs(),
            self.unsure_idxs(),
            self.col.processor.nr_total,
            self.ordering_to_cnt,
        )

    def nr_unsure(self):
        if len(self.idx_to_score) == 0:
            return 0
        return sum(
            1 for score in self.idx_to_score.values() if self.lower < score < self.upper
        )

    def nrs_with_temp_bounds(self, lower, upper):
        nr_t = sum(1 for score in self.idx_to_score.values() if score >= upper)
        nr_f = sum(1 for score in self.idx_to_score.values() if score <= lower)
        nr_u = sum(1 for score in self.idx_to_score.values() if lower < score < upper)
        return FilterResultNrs(
            nr_t, nr_f, nr_u, self.col.processor.nr_total, self.ordering_to_cnt
        )

    def estimate_nrs_tfu(self, weight):
        # New threshold.
        cur_score = self.lower * (1 - weight) + self.upper * weight
        # When user answers yes.
        nrs_yes = self.nrs_with_temp_bounds(self.lower, cur_score)
        # When user answers no.
        nrs_no = self.nrs_with_temp_bounds(cur_score, self.upper)
        return nrs_yes, nrs_no
