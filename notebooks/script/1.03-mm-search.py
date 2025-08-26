#!/usr/bin/env python
# coding: utf-8

import json 
from mksense.config import PROCESSED_DATA_DIR
repo = "scikit-learn"
doc_input_path = PROCESSED_DATA_DIR / repo / f"{repo}_docs_cleaned.json"
with open(doc_input_path, 'rt') as  f_in:
    documents = json.load(f_in)


documents[0]


import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
base_url=os.environ.get("BASE_URL")
api_key=os.environ.get("API_KEY")

llm_client = OpenAI(
    base_url=base_url,
    api_key=api_key,
)


def build_prompt(query, search_results):
    prompt_template = """
    Your are a vertern software developer. 
    Answer the QUESTION based on the CONTEXT from the documentation database. 
    Use only the facts from the CONTEXT when answering the QUESTION. 
    If the CONTEXT doesn't containt the answer output None.

    QUESTION:
    {question}

    CONTEXT:
    {context}
    """.strip()

    context = ""

    for doc in search_results:
        context = context + f"repo: {doc['repo']}\ntitle:{doc['title']}\ndocument: {doc['content']}\n\n"

    prompt = prompt_template.format(question=query, context=context).strip()

    return prompt 


def llm(prompt):
    responce = llm_client.chat.completions.create(
        model="deepseek/deepseek-r1-0528:free",
        messages=[{
            "role":"user",
            "content":prompt
        }]
    )
    return responce.choices[0].message.content


query = "how do I install scikit-learn"


# ```bash
#  docker run -it \
#    --rm \
#    --name elasticsearch \
#    -m 4GB \
#    -p 9200:9200 \
#    -p 9300:9300 \
#    -e "discovery.type=single-node" \
#    -e "xpack.security.enabled=false" \
#    elasticsearch:9.1.2
# ```
# 
# run elastic searrch with this docker code
# 
# or run the following function:
# 
# ```bash
# docker compose up -d
# ```

from elasticsearch import Elasticsearch
es_client = Elasticsearch('http://localhost:9200')


es_client.info()


index_settings = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "content": {"type": "text"},
            "file_path": {"type": "text"},
            "title": {"type": "text"},
            "context": {"type": "text"},
            "extension": {"type": "text"},
            "repo": {"type": "text"} 
        }
    }
}

index_name = "sklearn-docs"

es_client.indices.create(index=index_name, body=index_settings)


from tqdm.auto import tqdm
for doc in tqdm(documents):
    es_client.index(index=index_name, document=doc)


def elastic_search(query):
    search_query = {
        "size": 5,
        "query": {
            "bool": {
                "must": {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^3", "content", "context"],
                        "type": "best_fields"
                    }
                },
                "filter": {
                    "term": {
                        "repo": "scikit-learn"
                    }
                }
            }
        }
    }

    response = es_client.search(index=index_name, body=search_query)

    result_docs = []

    for hit in response['hits']['hits']:
        result_docs.append(hit['_source'])

    return result_docs


def rag(query):
    search_results = elastic_search(query)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt)
    return answer


query = "how do I install scikit-learn?"
rag(query)


# ```bash
# docker pull qdrant/qdrant
# 
# docker run -p 6333:6333 -p 6334:6334 \
#    -v "$(pwd)/data/qdrant_storage:/qdrant/storage:z" \
#    qdrant/qdrant
# ```
# 
# start the qd_client
# 
# if you added the docker compose DO NOT need to run this.

from qdrant_client import QdrantClient, models
from mksense.config import PROCESSED_DATA_DIR

qd_client = QdrantClient('http://localhost:6333')

EMBEDDING_DIMENSIONALITY  = 512

model_handle = "jinaai/jina-embeddings-v2-small-en"

# Define the collection name
collection_name = 'scikit-learn_docs'


qd_client.delete_collection(collection_name=collection_name)


# Create the collection with the specific vector parameters
qd_client.create_collection(
    collection_name=collection_name,
    vectors_config=models.VectorParams(
        size=EMBEDDING_DIMENSIONALITY, # Dimensionality of the vectors
        distance=models.Distance.COSINE # Distance metrics of the vectors
    )
)


qd_client.create_payload_index(
    collection_name=collection_name,
    field_name="repo",
    field_schema="keyword"
)


documents[0]


points = []

for i, doc in enumerate(documents):
    text = doc['title'] + ' ' + doc['content'] 
    vector = models.Document(text=text, model=model_handle)
    point = models.PointStruct(
        id=i,
        vector=vector, 
        payload=doc  
    )
    points.append(point)


points[0]


qd_client.upsert(
    collection_name=collection_name,
    points=points
)


def vector_search(query):
    print('Vector Seaach is Used')
    course = 'data-engineering-zoomcamp'
    query_points = qd_client.query_points(
        collection_name=collection_name,
        query=models.Document(  #embedded the query text locally with jinaai
            text=query,
            model=model_handle
        ),
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="course",
                    match=models.MatchValue(value=course)
                )
            ]
        ),
        limit=5,
        with_payload=True
    )

    results = []

    for point in query_points.points:
        results.append(point.payload)

    return results 


search_results = vector_search(query)


def rag(query):
    search_results = vector_search(query)
    prompt = build_prompt(query, search_results)
    answer = llm(prompt)
    return answer


query = "how do I run kafka?"
rag(query)

