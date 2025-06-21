# orchestration/vector_search_utils.py

class VectorSearchUtils:
    """
    Utilities for vector search and embedding-related query preparation.
    """

    def __init__(self, get_response_from_model, logger, embedding_model_token_limit=8190):
        self.get_response_from_model = get_response_from_model
        self.logger = logger
        self.embedding_model_token_limit = embedding_model_token_limit

    async def generate_concise_query_for_embedding(self, client, long_query_text: str, target_model: str = "gpt-4o-mini") -> str:
        """
        Generates a concise summary of a long text, suitable for use as an embedding query.
        """
        self.logger.warning(f"Original query length ({len(long_query_text)} chars) exceeds limit. Generating concise query.")

        max_summary_input_chars = 16000 * 4  # Rough estimate: 4 chars/token
        if len(long_query_text) > max_summary_input_chars:
            self.logger.warning(
                f"Truncating input for summarization model from {len(long_query_text)} to {max_summary_input_chars} chars."
            )
            long_query_text = long_query_text[:max_summary_input_chars] + "..."

        system_message = (
            "You are an expert at summarizing long texts into concise search queries.\n"
            "Analyze the following text and extract the core question, topic, or instruction.\n"
            "Your output should be a short phrase or sentence (ideally under 100 words, definitely under 500 tokens)\n"
            "that captures the essence of the text and is suitable for a semantic database search.\n"
            "Focus on the key entities, concepts, and the user's likely goal.\n"
            "Respond ONLY with the concise search query, no preamble or explanation."
        )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": long_query_text},
        ]

        try:
            concise_query, _, _ = await self.get_response_from_model(
                client=client,
                model=target_model,
                messages=messages,
                temperature=0.1,
            )

            if concise_query:
                self.logger.info(f"Generated concise query: {concise_query}")
                return concise_query.strip()
            else:
                self.logger.error(
                    "Failed to generate concise query (model returned empty). Falling back to truncation."
                )
                max_chars = self.embedding_model_token_limit * 3  # Very rough estimate
                return long_query_text[:max_chars]

        except Exception as e:
            self.logger.error(
                f"Error generating concise query: {str(e)}. Falling back to truncation."
            )
            max_chars = self.embedding_model_token_limit * 3
            return long_query_text[:max_chars]
