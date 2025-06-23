import logging
import tiktoken

def estimate_token_count(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Estimate the number of tokens in a text using tiktoken for OpenAI models.
    """
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def extract_user_assistant_content(messages, max_turns=5):
    """
    Extracts the last max_turns user/assistant messages for context.
    """
    filtered = [m for m in messages if m['role'] in ('user', 'assistant')]
    return ' '.join(m['content'] for m in filtered[-max_turns:])

def extract_system_message(messages):
    """
    Extracts the first system message content, if present.
    """
    for m in messages:
        if m['role'] == 'system':
            return m['content']
    return ""

async def summarize_text(
    text,
    openai_client,
    logger: logging.Logger = None,
    model: str = "gpt-3.5-turbo",
    max_tokens: int = 64,
    prompt: str = "Summarize the following text:"
) -> str:
    """
    Summarize the given text using OpenAI.
    """
    summary_prompt = [
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": text
        }
    ]
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=summary_prompt,
            max_tokens=max_tokens,
            temperature=0.3
        )
        summary = response.choices[0].message.content.strip()
        if logger:
            logger.info(f"Intermediate summary: {summary}")
        return summary
    except Exception as e:
        if logger:
            logger.error(f"Error during summarization: {e}")
        # Fallback: truncate text
        return text[:max_tokens * 4]  # Rough estimate

async def generate_summary_title(
    messages,
    openai_client,
    logger: logging.Logger = None,
    model: str = "gpt-4o-mini",
    max_tokens: int = 10,
    temperature: float = 0.5,
    token_limit: int = 4000,
    summary_model: str = "gpt-3.5-turbo",
    summary_max_tokens: int = 64,
) -> str:
    """
    Generate a short summary/title for a conversation using the OpenAI API.

    - Summarizes the system message and conversation context separately if needed.
    - Presents both to the title generator with explicit markers.
    - Uses tiktoken for accurate token counting.

    Args:
        messages (list): List of message dicts with 'content' keys.
        openai_client: An instance of OpenAI client.
        logger (logging.Logger, optional): Logger for info/debug.
        model (str): Model to use for summary generation.
        max_tokens (int): Max tokens for the summary.
        temperature (float): Sampling temperature.
        token_limit (int): Truncation limit for conversation history.
        summary_model (str): Model to use for summarization if needed.
        summary_max_tokens (int): Max tokens for the intermediate summary.

    Returns:
        str: The generated summary/title.
    """
    # 1. Extract and possibly summarize the system message
    system_message = extract_system_message(messages)
    if system_message:
        sys_tokens = estimate_token_count(system_message, model=summary_model)
        if sys_tokens > token_limit // 4:
            if logger:
                logger.info("System message too long, summarizing.")
            system_message_summary = await summarize_text(
                system_message,
                openai_client,
                logger=logger,
                model=summary_model,
                max_tokens=summary_max_tokens,
                prompt="Summarize the following system message for context:"
            )
        else:
            system_message_summary = system_message
    else:
        system_message_summary = ""

    # 2. Extract and possibly summarize the conversation context
    context = extract_user_assistant_content(messages, max_turns=5)
    context_tokens = estimate_token_count(context, model=summary_model)
    if context_tokens > token_limit:
        if logger:
            logger.info("Conversation context too large, summarizing before title generation.")
        context = await summarize_text(
            context,
            openai_client,
            logger=logger,
            model=summary_model,
            max_tokens=summary_max_tokens,
            prompt="Summarize the following conversation in 1-2 sentences, focusing on the main topic or question."
        )

    # 3. Compose the prompt for title generation
    title_prompt_content = ""
    if system_message_summary:
        title_prompt_content += (
            "System Message Summary (for context):\n"
            f"{system_message_summary}\n\n"
        )
    title_prompt_content += (
        "Conversation Summary (last turns or summarized):\n"
        f"{context}\n\n"
        "Please create a very short (2-4 words) summary title for the above context."
    )

    summary_request_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": title_prompt_content
            }
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    if logger:
        logger.info(f"Sending summary request to OpenAI for conversation title: {str(summary_request_payload)[:200]}")

    try:
        response = openai_client.chat.completions.create(**summary_request_payload)
        summary = response.choices[0].message.content.strip()
        if logger:
            logger.info(f"Response from OpenAI for summary: {response}")
            logger.info(f"Generated conversation summary: {summary}")
    except Exception as e:
        if logger:
            logger.error(f"Error in generate_summary_title: {e}")
        summary = "Conversation Summary"  # Fallback title

    return summary
