# orchestration/llm_router.py

import os
import asyncio
import anthropic
from google.generativeai import GenerativeModel
import google.generativeai as genai
import tiktoken

class LLMRouter:
    def __init__(self, cerebras_client, logger):
        self.cerebras_client = cerebras_client
        self.logger = logger

    async def get_response_from_model(
        self, client, model, messages, temperature,
        reasoning_effort=None, extended_thinking=None, thinking_budget=None,
    ):
        """
        Routes the request to the correct LLM API based on the model name.
        No fallback between providers: errors are logged and returned directly.
        """
        self.logger.info(f"Getting response from model: {model}")
        self.logger.info(f"Temperature: {temperature}")
        self.logger.info(f"Number of messages: {len(messages)}")
        self.logger.info(f"Extended thinking: {extended_thinking}")
        self.logger.info(f"Thinking budget: {thinking_budget}")

        max_retries = 3
        retry_delay = 1

        async def handle_openai_request(payload):
            for attempt in range(max_retries):
                try:
                    if model == "o3-mini":
                        if "max_tokens" in payload:
                            payload["max_completion_tokens"] = payload.pop("max_tokens")
                        if reasoning_effort:
                            payload["reasoning_effort"] = reasoning_effort
                    response = client.chat.completions.create(**payload)
                    return response.choices[0].message.content.strip(), response.model, None
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise

        async def handle_gemini_request(model_name, contents, temperature):
            for attempt in range(max_retries):
                try:
                    gemini_model = GenerativeModel(model_name=model_name)
                    response = await asyncio.to_thread(
                        gemini_model.generate_content,
                        contents,
                        generation_config={"temperature": temperature}
                    )
                    return response.text, model_name, None
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise

        async def handle_cerebras_request(model_name, messages, temperature):
            for attempt in range(max_retries):
                try:
                    formatted_messages = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in messages
                    ]
                    self.logger.info(f"Sending request to Cerebras API with model: {model_name}")
                    self.logger.debug(f"Formatted messages: {formatted_messages}")

                    if self.cerebras_client is None:
                        self.logger.error("Cerebras client is None. API key may be missing or invalid.")
                        raise ValueError("Cerebras client is not initialized")

                    api_key = os.getenv("CEREBRAS_API_KEY")
                    if api_key:
                        masked_key = f"{api_key[:4]}...{api_key[-4:]}"
                        self.logger.info(f"Using Cerebras API key: {masked_key}")
                    else:
                        self.logger.error("CEREBRAS_API_KEY environment variable is not set")
                        raise ValueError("CEREBRAS_API_KEY environment variable is not set")

                    response = self.cerebras_client.chat.completions.create(
                        messages=formatted_messages,
                        model=model_name,
                        temperature=temperature
                    )

                    self.logger.info(f"Received response from Cerebras API: {response}")
                    return response.choices[0].message.content, model_name, None
                except Exception as e:
                    self.logger.error(f"Error in Cerebras API call (attempt {attempt+1}): {str(e)}")
                    self.logger.exception("Full traceback:")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise

        try:
            if model.startswith("gpt-"):
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 4096
                }
                return await handle_openai_request(payload)

            elif model.startswith("claude-"):
                try:
                    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                    anthropic_messages = []
                    system_message = None
                    for message in messages:
                        if message['role'] == 'system':
                            system_message = message['content']
                        elif message['role'] in ['user', 'assistant']:
                            anthropic_messages.append({"role": message['role'], "content": message['content']})

                    if system_message and anthropic_messages:
                        anthropic_messages[0]['content'] = f"{system_message}\n\nUser: {anthropic_messages[0]['content']}"

                    if not anthropic_messages or anthropic_messages[0]['role'] != 'user':
                        anthropic_messages.insert(0, {"role": "user", "content": ""})

                    if model == "claude-3-7-sonnet-20250219":
                        max_tokens = 64000
                    elif model in ["claude-opus-4-20250514", "claude-sonnet-4-20250514"]:
                        max_tokens = 32000
                    else:
                        max_tokens = 4096

                    response = await asyncio.to_thread(
                        anthropic_client.messages.create,
                        model=model,
                        messages=anthropic_messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )

                    stop_reason = getattr(response, "stop_reason", None)
                    self.logger.info(f"Claude API stop_reason: {stop_reason}")

                    if stop_reason == "refusal":
                        refusal_message = (
                            "The model refused to answer this request for safety reasons."
                        )
                        return refusal_message, model, None

                    response_content = response.content[0].text if hasattr(response, "content") and response.content else ""
                    return response_content, model, None

                except Exception as e:
                    self.logger.error(f"Error in Claude API call: {str(e)}")
                    self.logger.exception("Full traceback:")
                    raise

            elif model.startswith("gemini-"):
                contents = [{
                    "role": "user",
                    "parts": [{"text": "\n".join([m['content'] for m in messages])}]
                }]
                return await handle_gemini_request(model, contents, temperature)

            elif model == "o3-mini":
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 4096
                }
                if reasoning_effort:
                    payload["reasoning_effort"] = reasoning_effort
                return await handle_openai_request(payload)

            elif model.startswith("llama3") or model == "llama-3.3-70b" or model == "deepSeek-r1-distill-llama-70B":
                if self.cerebras_client is None:
                    self.logger.error("Cerebras client not initialized. Please set CEREBRAS_API_KEY environment variable.")
                    raise ValueError("Cerebras client not initialized. Please set CEREBRAS_API_KEY environment variable.")

                self.logger.info(f"Routing request to Cerebras API for model: {model}")
                return await handle_cerebras_request(model, messages, temperature)

            else:
                self.logger.error(f"Unsupported model: {model}")
                raise ValueError(f"Unsupported model: {model}")

        except Exception as e:
            self.logger.error(f"Error getting response from model {model}: {str(e)}")
            self.logger.exception("Full traceback:")
            return None, None, None


# --------------------- Count Tokens for Different Models ---------------------

def approximate_gemini_tokens(messages):
    """
    Approximate token count for Gemini when API call fails.
    Uses a more sophisticated approximation than simple word count.
    """
    num_tokens = 0
    for message in messages:
        if isinstance(message, dict):
            content = message.get('content', '')
        elif isinstance(message, str):
            content = message
        else:
            continue

        char_count = len(content)
        word_count = len(content.split())
        token_estimate = (char_count / 4 + word_count * 1.3) / 2
        num_tokens += int(token_estimate)

    return num_tokens

def count_tokens(model_name, messages, logger=None):
    if model_name.startswith("gpt-"):
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        for message in messages:
            num_tokens += len(encoding.encode(message['content']))
            num_tokens += 4
            if 'name' in message:
                num_tokens += len(encoding.encode(message['name']))
        num_tokens += 2
        return num_tokens

    elif model_name.startswith("claude-"):
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        for message in messages:
            if isinstance(message, dict):
                content = message.get('content', '')
                role = message.get('role', '')
            elif isinstance(message, str):
                content = message
                role = ''
            else:
                continue
            num_tokens += len(encoding.encode(content))
            if role:
                num_tokens += len(encoding.encode(role))
            if role == 'user':
                num_tokens += len(encoding.encode("Human: "))
            elif role == 'assistant':
                num_tokens += len(encoding.encode("Assistant: "))
            num_tokens += 2
        if messages and isinstance(messages[0], dict) and messages[0].get('role') == 'system':
            num_tokens += len(encoding.encode("\n\nHuman: "))
        return num_tokens

    elif model_name.startswith("gemini-"):
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is not set")
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')
            num_tokens = 0
            for message in messages:
                if isinstance(message, dict):
                    content = message.get('content', '')
                elif isinstance(message, str):
                    content = message
                else:
                    continue
                token_count = model.count_tokens(content)
                num_tokens += token_count.total_tokens
            return num_tokens
        except Exception as e:
            if logger:
                logger.error(f"Error counting tokens for Gemini: {e}")
            return approximate_gemini_tokens(messages)

    elif model_name.startswith("llama3.1") or model_name == "llama-3.3-70b" or model_name == "deepSeek-r1-distill-llama-70B":
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = 0
        for message in messages:
            if isinstance(message, dict):
                content = message.get('content', '')
                role = message.get('role', '')
            elif isinstance(message, str):
                content = message
                role = ''
            else:
                continue
            num_tokens += len(encoding.encode(content))
            if role:
                num_tokens += len(encoding.encode(role))
            num_tokens += 4
        return num_tokens

    else:
        num_tokens = 0
        for message in messages:
            num_tokens += len(message['content'].split())
        return num_tokens
