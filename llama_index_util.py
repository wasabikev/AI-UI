from llama_index import GPTIndex


# Initialize the index
index = GPTIndex()

def add_to_index(data):
    # Add data to the index
    index.add(data)

def query_index(query):
    # Query the index
    results = index.query(query)
    return results
