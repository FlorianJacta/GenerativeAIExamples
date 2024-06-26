# SPDX-FileCopyrightText: Copyright (c) 2023-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import streamlit as st
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import UnstructuredFileLoader

from vectorstore.custom_powerpoint_parser import process_ppt_file
from vectorstore.custom_pdf_parser import get_pdf_documents

progress_for_logs = {}
CUSTOM_PROCESSING = True

def load_documents(folder):
    """Load documents from the specified folder."""
    raw_documents = []
    for file in os.listdir(folder):
        print("Loading document: ", file)
        file_path = os.path.join(folder, file)

        if file.endswith("pdf") and CUSTOM_PROCESSING:
            # Process each PDF document and add them individually to the list
            pdf_docs = get_pdf_documents(file_path)
            for each_page in pdf_docs:
                raw_documents.extend(each_page)
        elif file.endswith("ppt") or file.endswith("pptx"):
            pptx_docs = process_ppt_file(file_path)
            raw_documents.extend(pptx_docs)
        else:
            # Load unstructured files and add them individually
            loader = UnstructuredFileLoader(file_path)
            unstructured_docs = loader.load()
            raw_documents.extend(unstructured_docs)  # 'extend' is used here to add elements of the list individually
    return raw_documents

def split_text(documents):
    """Split text documents into chunks."""
    text_splitter = RecursiveCharacterTextSplitter(
        # Set a really small chunk size, just to show.
        chunk_size = 1000,
        chunk_overlap  = 100,
        length_function = len,
        is_separator_regex = False,
    )
    split_docs = text_splitter.split_documents(documents)
    return split_docs

def update_vectorstore(folder, vector_client, embedder, config_name, state_id):
    global progress_for_logs
    progress_for_logs[state_id] = {'retraining_logs' : []}
    progress_for_logs[state_id]['retraining_logs'].append("[Step 1/4] Creating/loading vector store")

    # Get embedding size from your embedder
    embedding_size = embedder.get_embedding_size()

    # Check if the collection exists
    progress_for_logs[state_id]['retraining_logs'].append("Creating collection...")
    vector_client.create_collection(config_name, embedding_size)

    progress_for_logs[state_id]['retraining_logs'].append("[Step 2/4] Processing and splitting documents")
    # load and split documents
    raw_documents = load_documents(folder)
    documents = split_text(raw_documents)

    progress_for_logs[state_id]['retraining_logs'].append("Loading data to the vector index store...")
    progress_for_logs[state_id]['retraining_logs'].append("[Step 3/4] Inserting documents into the vector store...")
    # Extracting the page content from each document
    document_contents = [doc.page_content for doc in documents]

    # Embedding the documents using the updated embedding function
    document_embeddings = embedder.embed_documents(document_contents, batch_size=10)

    # Batch insert into Milvus collection
    vector_client.update(documents, document_embeddings, config_name)
    progress_for_logs[state_id]['retraining_logs'].append("[Step 4/4] Saved vector store!")
