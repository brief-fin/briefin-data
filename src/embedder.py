from FlagEmbedding import BGEM3FlagModel

_model = None


def get_model() -> BGEM3FlagModel:
    global _model
    if _model is None:
        print("[embedder] BAAI/bge-m3 모델 로딩 중...")
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
        print("[embedder] 모델 로딩 완료")
    return _model


def embed(text: str) -> list[float]:
    """텍스트를 1024차원 벡터로 임베딩"""
    model = get_model()
    result = model.encode(text, batch_size=1, max_length=8192)
    import numpy as np
    return np.array(result["dense_vecs"]).flatten().tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """배치 임베딩"""
    model = get_model()
    result = model.encode(texts, batch_size=8, max_length=8192)
    return [vec.tolist() for vec in result["dense_vecs"]]
