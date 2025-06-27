# orchestration/chat_orchestrator.py

import os
import re
import json
import time
import tiktoken
from datetime import datetime, timezone
from sqlalchemy import select

class ChatOrchestrator:
    def __init__(
        self,
        *,
        status_manager,
        embedding_store,
        file_processor,
        session_attachment_handler,
        get_session,
        Conversation,
        SystemMessage,
        generate_summary_title,
        count_tokens,
        get_response_from_model,
        perform_web_search_process,
        EMBEDDING_MODEL_TOKEN_LIMIT,
        generate_concise_query_for_embedding,
        client,
        BRAVE_SEARCH_API_KEY,
        file_utils,
        logger,
    ):
        self.status_manager = status_manager
        self.embedding_store = embedding_store
        self.file_processor = file_processor
        self.session_attachment_handler = session_attachment_handler
        self.get_session = get_session
        self.Conversation = Conversation
        self.SystemMessage = SystemMessage
        self.generate_summary_title = generate_summary_title
        self.count_tokens = count_tokens
        self.get_response_from_model = get_response_from_model
        self.perform_web_search_process = perform_web_search_process
        self.EMBEDDING_MODEL_TOKEN_LIMIT = EMBEDDING_MODEL_TOKEN_LIMIT
        self.generate_concise_query_for_embedding = generate_concise_query_for_embedding
        self.client = client
        self.BRAVE_SEARCH_API_KEY = BRAVE_SEARCH_API_KEY
        self.file_utils = file_utils
        self.logger = logger

    async def run_chat(
        self,
        *,
        messages,
        model,
        temperature,
        system_message_id,
        enable_web_search,
        enable_deep_search,
        conversation_id,
        user_timezone,
        extended_thinking,
        thinking_budget,
        file_ids,
        current_user,
        session_id,
        request_data,
        session,  # Pass in the Quart session object for updating conversation_id
    ):
        request_start_time = time.time()
        try:
            self.logger.info(f'[{session_id}] Received model: {model}, temperature: {temperature}, system_message_id: {system_message_id}, enable_web_search: {enable_web_search}, enable_deep_search: {enable_deep_search}')
            params_extracted_time = time.time()

            await self.status_manager.update_status(
                message="Initializing conversation",
                session_id=session_id
            )

            # Fetch conversation if conversation_id is provided
            conversation = None
            if conversation_id:
                async with self.get_session() as db_session:
                    result = await db_session.execute(
                        select(self.Conversation).where(self.Conversation.id == conversation_id)
                    )
                    conversation = result.scalar_one_or_none()

                    if conversation and conversation.user_id == current_user.id:
                        self.logger.info(f'[{session_id}] Using existing conversation with id {conversation_id}.')
                    else:
                        self.logger.info(f'[{session_id}] No valid conversation found with id {conversation_id}, starting a new one.')
                        conversation = None
            conv_fetch_time = time.time()

            # Fetch system message to check if time sense is enabled
            async with self.get_session() as db_session:
                result = await db_session.execute(
                    select(self.SystemMessage).where(self.SystemMessage.id == system_message_id)
                )
                db_system_message = result.scalar_one_or_none()
                if not db_system_message:
                    self.logger.error(f"[{session_id}] System message with ID {system_message_id} not found")
                    return {'error': 'System message not found'}, 404
                enable_time_sense = db_system_message.enable_time_sense
                self.logger.info(f"[{session_id}] Time sense enabled: {enable_time_sense}")
            sys_msg_fetch_time = time.time()

            system_message = next((msg for msg in messages if msg['role'] == 'system'), None)

            # --- Session Attachment Injection (Before Time Context) ---
            original_user_query_text = messages[-1]['content']
            user_query_for_semantic_search = original_user_query_text
            injected_attachment_content = ""
            context_block_regex = r"\n*--- Attached Files Context ---[\s\S]*?--- End Attached Files Context ---\n*"

            if file_ids:
                self.logger.info(f"[{session_id}] Found {len(file_ids)} session attachment IDs. Processing content.")
                await self.status_manager.update_status(
                    message="Processing session attachments...",
                    session_id=session_id
                )
                retrieved_contents = []
                filenames_processed = []
                for attachment_id in file_ids:
                    self.logger.debug(f"[{session_id}] Attempting to get content for attachment ID: {attachment_id}")
                    content, filename, _ = await self.session_attachment_handler.get_attachment_content(attachment_id, current_user.id, system_message_id)
                    if content:
                        filename_placeholder = filename or f"Attachment ID {attachment_id[:8]}"
                        filenames_processed.append(filename_placeholder)
                        # If content is bytes, decode as utf-8 with fallback
                        if isinstance(content, bytes):
                            try:
                                content = content.decode('utf-8')
                            except Exception:
                                content = content.decode('latin1', errors='replace')
                        retrieved_contents.append(
                            f"\n--- Content from {filename_placeholder} ---\n{content}\n--- End Content from {filename_placeholder} ---"
                        )
                        self.logger.info(f"[{session_id}] Successfully retrieved content for attachment: {filename_placeholder} (ID: {attachment_id})")
                    else:
                        self.logger.warning(f"[{session_id}] Could not retrieve content for session attachment ID: {attachment_id}")

                if retrieved_contents:
                    injected_attachment_content = "\n".join(retrieved_contents)
                    user_text_without_block = re.sub(context_block_regex, "", original_user_query_text).strip()
                    self.logger.debug(f"[{session_id}] User text after removing placeholder block: '{user_text_without_block[:100]}...'")
                    messages[-1]['content'] = (user_text_without_block + "\n\n" + injected_attachment_content).strip()
                    self.logger.info(f"[{session_id}] Injected content from {len(retrieved_contents)} session attachments into user message for AI.")
                    self.logger.debug(f"[{session_id}] Updated user message content for AI (truncated): {messages[-1]['content'][:200]}...")
                    user_query_for_semantic_search = user_text_without_block
                else:
                    self.logger.warning(f"[{session_id}] No content retrieved for provided attachment IDs. User message unchanged.")
                    user_query_for_semantic_search = re.sub(context_block_regex, "", original_user_query_text).strip()
            else:
                user_query_for_semantic_search = re.sub(context_block_regex, "", original_user_query_text).strip()
            # --- End Session Attachment Injection ---

            # --- Time Context ---
            time_context_start_time = time.time()
            if enable_time_sense and messages:
                self.logger.info(f"[{session_id}] ===== BEFORE TIME CONTEXT PROCESSING =====")
                self.logger.info(f"[{session_id}] Enable time sense: {enable_time_sense}")
                from utils.time_utils import clean_and_update_time_context
                time_context_user = {'timezone': user_timezone}
                if enable_time_sense:
                    await self.status_manager.update_status(
                        message="Processing time context information",
                        session_id=session_id
                    )
                    self.logger.info(f"[{session_id}] About to call clean_and_update_time_context")
                    messages = await clean_and_update_time_context(
                        messages,
                        time_context_user,
                        enable_time_sense,
                        self.logger
                    )
                    self.logger.info(f"[{session_id}] After calling clean_and_update_time_context")
                    self.logger.info(f"[{session_id}] Time context processing completed")
                system_message = next((msg for msg in messages if msg['role'] == 'system'), None)
                if not system_message:
                    system_message = {"role": "system", "content": ""}
                    messages.insert(0, system_message)
                    self.logger.info(f"[{session_id}] Created new system message after time context processing")
            time_context_end_time = time.time()

            self.logger.info(f'[{session_id}] Getting storage context for system_message_id: {system_message_id}')
            await self.status_manager.update_status(
                message="Checking document database",
                session_id=session_id
            )

            user_query = user_query_for_semantic_search
            self.logger.info(f'[{session_id}] User query for semantic search (first 50 chars): {user_query[:50]}')
            query_extracted_time = time.time()

            # --- Semantic Search Section ---
            semantic_search_start_time = time.time()
            relevant_info = None
            semantic_search_query = user_query
            user_query_embedding_tokens = 0

            try:
                embedding_encoding = tiktoken.get_encoding("cl100k_base")
                user_query_embedding_tokens = len(embedding_encoding.encode(user_query))
                self.logger.info(f"[{session_id}] Estimated token count for embedding query: {user_query_embedding_tokens}")

                if user_query_embedding_tokens > self.EMBEDDING_MODEL_TOKEN_LIMIT:
                    self.logger.warning(f"[{session_id}] Query token count ({user_query_embedding_tokens}) exceeds limit ({self.EMBEDDING_MODEL_TOKEN_LIMIT}).")
                    await self.status_manager.update_status(
                        message="Query is too long for semantic search, generating concise version...",
                        session_id=session_id
                    )
                    semantic_search_query = await self.generate_concise_query_for_embedding(self.client, user_query)
                    concise_query_tokens = len(embedding_encoding.encode(semantic_search_query))
                    self.logger.info(f"[{session_id}] Concise query generated (length {len(semantic_search_query)} chars, {concise_query_tokens} tokens).")
                    if concise_query_tokens > self.EMBEDDING_MODEL_TOKEN_LIMIT:
                        self.logger.warning(f"[{session_id}] Concise query still too long ({concise_query_tokens} tokens). Truncating further.")
                        max_chars = self.EMBEDDING_MODEL_TOKEN_LIMIT * 3
                        semantic_search_query = semantic_search_query[:max_chars]
                        self.logger.info(f"[{session_id}] Truncated concise query to {len(semantic_search_query)} chars.")
            except tiktoken.EncodingError as enc_error:
                self.logger.error(f"[{session_id}] Tiktoken encoding error: {enc_error}. Cannot estimate tokens accurately.")
                user_query_embedding_tokens = len(user_query) // 3
                self.logger.warning(f"[{session_id}] Using rough token estimate: {user_query_embedding_tokens}")
            except Exception as token_error:
                self.logger.error(f"[{session_id}] Error estimating token count for embedding query: {token_error}. Proceeding with original query, may fail.")
                user_query_embedding_tokens = len(user_query.split())

            if user_query_embedding_tokens <= self.EMBEDDING_MODEL_TOKEN_LIMIT * 1.5:
                try:
                    self.logger.info(f'[{session_id}] Querying index with semantic search query (length {len(semantic_search_query)} chars): {semantic_search_query[:100]}...')
                    await self.status_manager.update_status(
                        message="Searching through documents",
                        session_id=session_id
                    )
                    if self.embedding_store is None:
                        self.logger.error(f"[{session_id}] Embedding store is not initialized!")
                        raise RuntimeError("Embedding store not ready")
                    if self.file_processor is None:
                        self.logger.error(f"[{session_id}] File processor is not initialized!")
                        raise RuntimeError("File processor not ready")
                    storage_context = await self.embedding_store.get_storage_context(system_message_id)
                    relevant_info = await self.file_processor.query_index(semantic_search_query, storage_context)
                    if relevant_info:
                        self.logger.info(f'[{session_id}] Retrieved relevant info (first 100 chars): {str(relevant_info)[:100]}')
                        await self.status_manager.update_status(message="Found relevant information in documents", session_id=session_id)
                    else:
                        self.logger.info(f'[{session_id}] No relevant information found in the index.')
                        await self.status_manager.update_status(message="No relevant documents found", session_id=session_id)
                        relevant_info = None
                except RuntimeError as init_error:
                    await self.status_manager.update_status(message=f"Error during setup: {init_error}", session_id=session_id, status="error")
                    relevant_info = None
                except Exception as e:
                    self.logger.error(f'[{session_id}] Error querying index: {str(e)}')
                    await self.status_manager.update_status(message="Error searching document database", session_id=session_id, status="error")
                    relevant_info = None
            else:
                self.logger.warning(f"[{session_id}] Skipping semantic search because query is too long ({user_query_embedding_tokens} tokens) even after potential summarization.")
                await self.status_manager.update_status(message="Skipping document search as the query is too long.", session_id=session_id)
                relevant_info = None

            semantic_search_end_time = time.time()

            if system_message is None:
                system_message = {"role": "system", "content": ""}
                messages.insert(0, system_message)

            if relevant_info:
                self.logger.info(f"[{session_id}] Injecting relevant document info into system message.")
                system_message['content'] += f"\n\n<Added Context Provided by Vector Search>\n{relevant_info}\n</Added Context Provided by Vector Search>"
            else:
                self.logger.info(f"[{session_id}] No relevant document info to inject.")

            summarized_results = None
            generated_search_queries = None

            # --- Web Search Section ---
            web_search_start_time = time.time()
            if enable_web_search:
                try:
                    self.logger.info(f'[{session_id}] Web search enabled, starting search process')
                    await self.status_manager.update_status(
                        message="Starting web search process",
                        session_id=session_id
                    )
                    generated_search_queries, summarized_results = await self.perform_web_search_process(
                        self.client,
                        model,
                        messages,
                        user_query,
                        current_user.id,
                        system_message_id,
                        enable_deep_search,
                        session_id,
                        status_manager=self.status_manager,
                        logger=self.logger,
                        get_response_from_model=self.get_response_from_model,
                        BRAVE_SEARCH_API_KEY=self.BRAVE_SEARCH_API_KEY,
                        get_file_path=self.file_utils.get_file_path
                    )
                    await self.status_manager.update_status(
                        message="Web search completed, processing results",
                        session_id=session_id
                    )
                    self.logger.info(f'[{session_id}] Web search process completed. Generated queries: {generated_search_queries}')
                    self.logger.info(f'[{session_id}] Summarized results (first 100 chars): {summarized_results[:100] if summarized_results else None}')
                    if not isinstance(generated_search_queries, list):
                        self.logger.warning(f"[{session_id}] generated_search_queries is not a list. Type: {type(generated_search_queries)}. Value: {generated_search_queries}")
                        generated_search_queries = [str(generated_search_queries)] if generated_search_queries else []
                    if summarized_results:
                        self.logger.info(f"[{session_id}] Injecting web search results into system message.")
                        system_message['content'] += f"\n\n<Added Context Provided by Web Search>\n{summarized_results}\n</Added Context Provided by Web Search>"
                        system_message['content'] += "\n\nIMPORTANT: In your response, please include relevant footnotes using [1], [2], etc. At the end of your response, list all sources under a 'Sources:' section, providing full URLs for each footnote."
                    else:
                        self.logger.warning(f'[{session_id}] No summarized results from web search to inject.')
                except Exception as e:
                    self.logger.error(f'[{session_id}] Error in web search process: {str(e)}')
                    await self.status_manager.update_status(
                        message="Error during web search process",
                        session_id=session_id,
                        status="error"
                    )
                    generated_search_queries = None
                    summarized_results = None
            else:
                self.logger.info(f'[{session_id}] Web search is disabled')
            web_search_end_time = time.time()

            self.logger.info(f"[{session_id}] Final system message (first 200 chars): {system_message['content'][:200]}")
            self.logger.info(f'[{session_id}] Sending final message list ({len(messages)} messages) to model.')

            await self.status_manager.update_status(
                message=f"Generating final analysis and response using model: {model}",
                session_id=session_id
            )

            # --- AI Model Call Section ---
            self.logger.info(f"[{session_id}] >>> Calling get_response_from_model for model {model}...")
            start_model_call_time = time.time()
            reasoning_effort = request_data.get('reasoning_effort')
            chat_output, model_name, thinking_process = await self.get_response_from_model(
                client=self.client,
                model=model,
                messages=messages,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                extended_thinking=extended_thinking if model == 'claude-3-7-sonnet-20250219' else None,
                thinking_budget=thinking_budget if model == 'claude-3-7-sonnet-20250219' and extended_thinking else None
            )
            end_model_call_time = time.time()
            model_call_duration = end_model_call_time - start_model_call_time
            self.logger.info(f"[{session_id}] <<< get_response_from_model completed. Duration: {model_call_duration:.2f}s")

            if chat_output is None:
                self.logger.error(f"[{session_id}] Failed to get response from model {model_name or model}.")
                await self.status_manager.update_status(
                    message="Error getting response from AI model",
                    session_id=session_id,
                    status="error"
                )
                raise Exception(f"Failed to get response from model {model_name or model}")
            else:
                self.logger.info(f"[{session_id}] Model returned output (first 100 chars): {chat_output[:100]}...")

            # --- Post-Processing and Saving ---
            post_process_start_time = time.time()
            prompt_tokens = self.count_tokens(model_name, messages)
            completion_tokens = self.count_tokens(model_name, [{"role": "assistant", "content": chat_output}])
            total_tokens = prompt_tokens + completion_tokens

            self.logger.info(f'[{session_id}] Tokens - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}')

            new_message = {"role": "assistant", "content": chat_output}
            messages.append(new_message)

            # Update or create conversation
            async with self.get_session() as db_session:
                try:
                    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                    if not conversation:
                        self.logger.info(f"[{session_id}] Creating new conversation.")
                        conversation = self.Conversation(
                            history=json.dumps(messages),
                            temperature=temperature,
                            user_id=current_user.id,
                            token_count=total_tokens,
                            created_at=current_time,
                            updated_at=current_time,
                            model_name=model_name
                        )
                        # Generate summary title (assume synchronous for now)
                        conversation_title = await self.generate_summary_title(messages, openai_client=self.client, logger=self.logger)
                        conversation.title = conversation_title

                        db_session.add(conversation)
                        self.logger.info(f'[{session_id}] Added new conversation with title: {conversation_title}')
                    else:
                        # Fetch fresh instance of existing conversation within this session
                        self.logger.info(f"[{session_id}] Updating existing conversation ID: {conversation.id}")
                        result = await db_session.execute(
                            select(self.Conversation).where(self.Conversation.id == conversation.id)
                        )
                        conversation = result.scalar_one_or_none()
                        if not conversation:
                            self.logger.error(f"[{session_id}] Failed to re-fetch conversation {conversation_id} before update.")
                            raise ValueError(f"Conversation {conversation_id} not found in database for update")
                        conversation.history = json.dumps(messages)
                        conversation.temperature = temperature
                        conversation.token_count += total_tokens
                        conversation.updated_at = current_time
                        conversation.model_name = model_name
                        self.logger.info(f'[{session_id}] Updated existing conversation with id: {conversation.id}')

                    # Set the additional fields consistently
                    conversation.vector_search_results = json.dumps(relevant_info) if relevant_info else None
                    conversation.generated_search_queries = json.dumps(generated_search_queries) if generated_search_queries else None
                    conversation.web_search_results = json.dumps(summarized_results) if summarized_results else None

                    await self.status_manager.update_status(
                        message="Saving conversation",
                        session_id=session_id
                    )

                    # Commit changes
                    await db_session.commit()
                    self.logger.info(f"[{session_id}] Conversation committed to database.")

                    # Refresh the instance to get the final state after commit (especially the ID if new)
                    await db_session.refresh(conversation)
                    final_conversation_id = conversation.id

                    # Update the session with the conversation ID
                    session['conversation_id'] = final_conversation_id

                    self.logger.info(f'[{session_id}] Chat response prepared. Conversation ID: {final_conversation_id}, Title: {conversation.title}')
                    db_save_end_time = time.time()

                    # Log detailed timings
                    self.logger.info(f"[{session_id}] --- Request Timing Breakdown ---")
                    self.logger.info(f"[{session_id}] Data Received: {params_extracted_time - request_start_time:.3f}s")
                    self.logger.info(f"[{session_id}] Conv Fetch: {conv_fetch_time - params_extracted_time:.3f}s")
                    self.logger.info(f"[{session_id}] Sys Msg Fetch: {sys_msg_fetch_time - conv_fetch_time:.3f}s")
                    if enable_time_sense:
                        self.logger.info(f"[{session_id}] Time Context Proc: {time_context_end_time - time_context_start_time:.3f}s")
                    self.logger.info(f"[{session_id}] Query Extraction: {query_extracted_time - sys_msg_fetch_time:.3f}s")
                    self.logger.info(f"[{session_id}] Semantic Search: {semantic_search_end_time - semantic_search_start_time:.3f}s")
                    if enable_web_search:
                        self.logger.info(f"[{session_id}] Web Search: {web_search_end_time - web_search_start_time:.3f}s")
                    self.logger.info(f"[{session_id}] AI Model Call: {model_call_duration:.3f}s")
                    self.logger.info(f"[{session_id}] Post-Processing & DB Save: {db_save_end_time - post_process_start_time:.3f}s")
                    self.logger.info(f"[{session_id}] Total Request Duration: {db_save_end_time - request_start_time:.3f}s")
                    self.logger.info(f"[{session_id}] --- End Timing Breakdown ---")

                    return {
                        'response': chat_output,
                        'conversation_id': final_conversation_id,
                        'conversation_title': conversation.title,
                        'vector_search_results': relevant_info if relevant_info else "No results found",
                        'generated_search_queries': generated_search_queries if generated_search_queries else [],
                        'web_search_results': summarized_results if summarized_results else "No web search performed",
                        'system_message_content': system_message['content'],
                        'thinking_process': thinking_process if thinking_process else None,
                        'usage': {
                            'prompt_tokens': prompt_tokens,
                            'completion_tokens': completion_tokens,
                            'total_tokens': total_tokens
                        },
                        'enable_web_search': enable_web_search,
                        'enable_deep_search': enable_deep_search,
                        'model_info': {
                            'name': model_name,
                            'extended_thinking': extended_thinking if model == 'claude-3-7-sonnet-20250219' else None,
                            'thinking_budget': thinking_budget if model == 'claude-3-7-sonnet-20250219' and extended_thinking else None
                        }
                    }

                except Exception as db_error:
                    self.logger.error(f'[{session_id}] Database error during save: {str(db_error)}')
                    await db_session.rollback()
                    raise

        except Exception as e:
            log_prefix = f"[{session_id}] " if session_id else ""
            self.logger.error(f'{log_prefix}Unexpected error in chat orchestrator: {str(e)}')
            self.logger.exception(f"{log_prefix}Full traceback for chat orchestrator error:")
            await self.status_manager.update_status(
                message="An error occurred during processing",
                session_id=session_id,
                status="error"
            )
            return {'error': 'An unexpected error occurred'}, 500

        finally:
            # Ensure the session is marked as inactive when the chat request processing ends (success or failure)
            if session_id:
                self.logger.info(f"[{session_id}] Cleaning up connection status for session.")
                await self.status_manager.remove_connection(session_id)
            else:
                self.logger.warning("No session ID available in finally block for cleanup.")

