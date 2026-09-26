"""Run the existing indexing tasks with metadata compatible with Chroma 0.5."""

from dotenv import load_dotenv

from src import task4_chunking_indexing as indexing


def main():
    load_dotenv(indexing.STANDARDIZED_DIR.parents[1] / ".env")
    documents = indexing.load_documents()
    chunks = indexing.chunk_documents(documents)
    if not chunks:
        raise ValueError("No standardized documents to index")
    for start in range(0, len(chunks), 100):
        embedded = indexing.embed_chunks(chunks[start:start + 100])
        # The task's URL may be None; this installed Chroma version requires
        # scalar metadata. Only the persisted representation is normalized.
        compatible = [{**chunk, "metadata": {
            key: value if value is not None else ""
            for key, value in chunk["metadata"].items()
        }} for chunk in embedded]
        indexing.index_to_vectorstore(compatible)
        print(f"Indexed {min(start + 100, len(chunks))}/{len(chunks)} chunks", flush=True)
    collection = indexing.get_collection()
    expected = {chunk["id"] for chunk in chunks}
    actual = set(collection.get(include=[])["ids"])
    stale = actual - expected
    if stale:
        collection.delete(ids=sorted(stale))
    assert set(collection.get(include=[])["ids"]) == expected
    print(f"Index ready: {len(documents)} documents, {collection.count()} chunks", flush=True)


if __name__ == "__main__":
    main()
