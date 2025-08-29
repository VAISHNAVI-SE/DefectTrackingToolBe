from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from collections import defaultdict
from dateutil.parser import parse

model = SentenceTransformer('all-MiniLM-L6-v2')

def convert_date_or_none(d):
    val = d.get('created_at')
    try:
        return parse(val) if val else None
    except Exception:
        return None

def ai_filter_unique_defects(defects, distance_threshold=0.65):
    if not defects:
        return []

    if len(defects) == 1:
        # Only one defect, return as is, no clustering needed
        return defects

    texts = [f"{d.get('summary', '')} {d.get('actual_result', '')} {d.get('expected_result', '')}"
        for d in defects
    ]
    embeddings = model.encode(texts, convert_to_numpy=True)

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric='cosine',
        linkage='average'
    )
    clustering.fit(embeddings)
    labels = clustering.labels_

    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        clusters[label].append(defects[idx])
    unique = []
    for group in clusters.values():
        oldest = min(group, key=lambda d: convert_date_or_none(d) or d.get('defect_id'))
        unique.append(oldest)
    return unique
