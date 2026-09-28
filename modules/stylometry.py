"""
Module 3 — STYLOMETRIC ANALYSIS
===============================

A REAL (if basic) authorship-similarity computation. Nothing here is hardcoded:
the scores change if you change the post text.

Two independent views of writing style are combined:

  1. Lexical/character view  — TF-IDF over character 3-5 grams, cosine similarity
     between the subject's concatenated corpus and each candidate actor's corpus.
     Character n-grams capture spelling, morphology and punctuation habits and
     are the standard cheap baseline in authorship attribution.

  2. Feature view — a vector of interpretable text statistics (mean sentence
     length, punctuation rates, uppercase rate, type-token ratio, function-word
     rate, contraction/digit rate) compared with a normalised distance.

Final score = 0.65 * n-gram cosine + 0.35 * feature similarity, calibrated onto
an investigator-facing 0-100 scale.
"""

import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from utils.helpers import calibrate, posts_of_actor, posts_of_persona

# Measured on this corpus: same-author char-n-gram cosine sits at 0.83-0.91,
# different-author at 0.10-0.34. Calibration stretches that observed band across
# the 0-100 display scale so the number is interpretable by an investigator.
# These constants are a DISPLAY calibration; the underlying cosine is unmodified
# and is reported alongside it in the evidence detail.
NGRAM_LOW, NGRAM_HIGH = 0.10, 0.90
FEATURE_LOW, FEATURE_HIGH = 0.25, 0.85

FUNCTION_WORDS = [
    "the", "of", "and", "to", "a", "in", "that", "it", "is", "was", "i", "for",
    "on", "with", "as", "be", "at", "by", "this", "not", "but", "or", "if",
    "would", "should", "shall", "whilst", "however", "therefore", "accordingly",
]


def text_features(text: str):
    """Interpretable style statistics, returned as a fixed-length vector."""
    words = re.findall(r"[a-zA-Z']+", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    n_words = max(len(words), 1)
    n_chars = max(len(text), 1)
    lens = [len(re.findall(r"[a-zA-Z']+", s)) for s in sentences] or [0]
    counts = Counter(text)
    lower = [w.lower() for w in words]

    return {
        "mean_sentence_len": float(np.mean(lens)),
        "sentence_len_sd": float(np.std(lens)),
        "mean_word_len": sum(len(w) for w in words) / n_words,
        "type_token_ratio": len(set(lower)) / n_words,
        "comma_rate": counts[","] / n_chars * 100,
        "period_rate": counts["."] / n_chars * 100,
        "exclaim_rate": counts["!"] / n_chars * 100,
        "question_rate": counts["?"] / n_chars * 100,
        "semicolon_rate": counts[";"] / n_chars * 100,
        "ellipsis_rate": text.count("...") / n_chars * 100,
        "uppercase_rate": sum(1 for c in text if c.isupper()) / n_chars * 100,
        "digit_rate": sum(1 for c in text if c.isdigit()) / n_chars * 100,
        "apostrophe_rate": counts["'"] / n_chars * 100,
        "function_word_rate": sum(lower.count(f) for f in FUNCTION_WORDS) / n_words * 100,
        "long_word_rate": sum(1 for w in words if len(w) >= 8) / n_words * 100,
    }


# scale factors keep every feature in a roughly comparable range
_SCALE = np.array([14.0, 8.0, 6.0, 1.0, 3.0, 4.0, 3.0, 2.0, 1.0, 1.0,
                   8.0, 4.0, 4.0, 60.0, 25.0])
_FEATURE_ORDER = list(text_features("Sample text. Another one!"))


def feature_vector(text: str) -> np.ndarray:
    f = text_features(text)
    return np.array([f[k] for k in _FEATURE_ORDER]) / _SCALE


def feature_similarity(a: str, b: str) -> float:
    va, vb = feature_vector(a), feature_vector(b)
    d = float(np.linalg.norm(va - vb))
    return 1.0 / (1.0 + d)          # 1.0 = identical style statistics


def _corpus(posts):
    return "\n".join(p["text"] for p in posts)


def analyse(ds, subject_id, actor_id, min_chars=120):
    """Stylometric similarity between subject persona and candidate actor."""
    subj_posts = posts_of_persona(ds, subject_id)
    act_posts = posts_of_actor(ds, actor_id)
    subj_text, act_text = _corpus(subj_posts), _corpus(act_posts)

    if len(subj_text) < min_chars or len(act_text) < min_chars:
        return {"score": None, "available": False, "evidence": [],
                "reason": "insufficient text for a stylometric comparison"}

    # --- view 1: TF-IDF character n-grams -------------------------------
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                          min_df=1, sublinear_tf=True, lowercase=True)
    m = vec.fit_transform([subj_text, act_text])
    num = float((m[0].multiply(m[1])).sum())
    den = float(np.sqrt(m[0].multiply(m[0]).sum()) * np.sqrt(m[1].multiply(m[1]).sum()))
    ngram_cos = num / den if den else 0.0

    # --- view 2: interpretable feature statistics -----------------------
    feat_sim = feature_similarity(subj_text, act_text)

    ngram_c = calibrate(ngram_cos, NGRAM_LOW, NGRAM_HIGH)
    feat_c = calibrate(feat_sim, FEATURE_LOW, FEATURE_HIGH)
    score = round(0.65 * ngram_c + 0.35 * feat_c, 1)

    sf, af = text_features(subj_text), text_features(act_text)
    evidence = [
        {"type": "char_ngram_cosine",
         "detail": f"TF-IDF char 3-5gram cosine = {ngram_cos:.3f} "
                   f"(calibrated {ngram_c:.1f})",
         "weight": round(ngram_cos, 3)},
        {"type": "style_statistics",
         "detail": f"mean sentence length {sf['mean_sentence_len']:.1f} vs "
                   f"{af['mean_sentence_len']:.1f} words; "
                   f"'!' rate {sf['exclaim_rate']:.2f} vs {af['exclaim_rate']:.2f}; "
                   f"TTR {sf['type_token_ratio']:.2f} vs {af['type_token_ratio']:.2f}",
         "weight": round(feat_sim, 3)},
    ]

    return {
        "score": score,
        "available": True,
        "evidence": evidence,
        "components": {"ngram_cosine_raw": round(ngram_cos, 4),
                       "ngram_calibrated": ngram_c,
                       "feature_similarity_raw": round(feat_sim, 4),
                       "feature_calibrated": feat_c},
        "subject_features": {k: round(v, 3) for k, v in sf.items()},
        "actor_features": {k: round(v, 3) for k, v in af.items()},
        "subject_post_count": len(subj_posts),
        "actor_post_count": len(act_posts),
    }
