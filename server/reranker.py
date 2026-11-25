"""CPU ONNX reranking without a PyTorch dependency in production."""
from huggingface_hub import hf_hub_download
from transformers import AutoTokenizer
import numpy as np
import onnxruntime as ort

class OnnxReranker:
    def __init__(self, model_name, revision='f7481e6055501a30fb19d090657df9ec1f79ab2c'):
        path = hf_hub_download(model_name, 'onnx/model_int8.onnx', revision=revision or None)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision or None)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        self.session = ort.InferenceSession(path, sess_options=options, providers=['CPUExecutionProvider'])
        self.inputs = {x.name for x in self.session.get_inputs()}

    def predict(self, pairs, batch_size=4):
        scores = []
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start:start+batch_size]
            data = self.tokenizer([p[0] for p in batch], [p[1] for p in batch], padding=True,
                                  truncation=True, max_length=512, return_tensors='np')
            feed = {k: np.asarray(v, dtype=np.int64) for k, v in data.items() if k in self.inputs}
            scores.extend(np.asarray(self.session.run(None, feed)[0]).reshape(-1).tolist())
        return scores
