# orchestration/image_generation.py

class ImageGenerationOrchestrator:
    def __init__(self, openai_client, logger):
        self.openai_client = openai_client
        self.logger = logger

    async def generate_image(self, prompt, n=1, size="256x256"):
        try:
            # OpenAI's image API is not async, so run in executor
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.Image.create(
                    prompt=prompt,
                    n=n,
                    size=size
                )
            )
            image_url = response['data'][0]['url']
            return {"success": True, "image_url": image_url}, 200
        except Exception as e:
            self.logger.error(f"Image generation failed: {str(e)}")
            return {"success": False, "error": str(e)}, 500
