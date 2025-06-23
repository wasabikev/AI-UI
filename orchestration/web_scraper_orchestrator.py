"""
This module is a future extension point for orchestrating web content extraction.
Traditional Scrapy-based scraping logic has been removed in favor of planned
AI-powered content extraction (e.g., via Firecrawl or similar).

Add implementation here when ready to support Firecrawl/web content orchestration.
"""

import logging
from sqlalchemy import select

class WebScraperOrchestrator:
    def __init__(self, logger: logging.Logger, get_session, SystemMessage, Website):
        self.logger = logger
        self.get_session = get_session
        self.SystemMessage = SystemMessage
        self.Website = Website

    async def add_website(self, url, system_message_id, current_user):
        if not url:
            return {'success': False, 'message': 'URL is required'}, 400
        if not system_message_id:
            return {'success': False, 'message': 'System message ID is required'}, 400
        if not url.startswith('http://') and not url.startswith('https://'):
            return {'success': False, 'message': 'Invalid URL format'}, 400

        async with self.get_session() as session:
            # Verify system message exists
            system_message_result = await session.execute(
                select(self.SystemMessage).filter_by(id=system_message_id)
            )
            system_message = system_message_result.scalar_one_or_none()
            if not system_message:
                return {'success': False, 'message': 'System message not found'}, 404

            # Optional: Only allow owner/admin to add websites
            is_admin = await current_user.is_admin
            if not is_admin and system_message.created_by != current_user.id:
                return {'success': False, 'message': 'Unauthorized to add website to this system message'}, 403


            new_website = self.Website(
                url=url,
                system_message_id=system_message_id,
                indexing_status='pending'
            )
            session.add(new_website)
            await session.commit()
            await session.refresh(new_website)

            self.logger.info(f"Website added: {url} for system_message_id={system_message_id} by user {current_user.id}")
            return {
                'success': True,
                'message': 'Website added successfully',
                'website': new_website.to_dict()
            }, 201

    async def remove_website(self, website_id, current_user):
        async with self.get_session() as session:
            result = await session.execute(
                select(self.Website).filter_by(id=website_id)
            )
            website = result.scalar_one_or_none()
            if not website:
                return {'success': False, 'message': 'Website not found'}, 404

            # Optional: Only allow owner/admin to remove
            system_message_id = website.system_message_id
            system_message_result = await session.execute(
                select(self.SystemMessage).filter_by(id=system_message_id)
            )
            system_message = system_message_result.scalar_one_or_none()
            is_admin = await current_user.is_admin
            if not is_admin and (not system_message or system_message.created_by != current_user.id):
                return {'success': False, 'message': 'Unauthorized to remove this website'}, 403

            await session.delete(website)
            await session.commit()
            self.logger.info(f"Website removed: id={website_id} by user {current_user.id}")
            return {'success': True, 'message': 'Website removed successfully'}, 200

    async def extract_content(self, url: str, **kwargs):
        """
        Placeholder for AI-powered web content extraction.

        Args:
            url (str): URL to extract content from

        Returns:
            dict: {
                "success": False,
                "message": "Not implemented"
            }
        """
        self.logger.info(f"extract_content called for URL: {url} (not implemented)")
        return {
            "success": False,
            "message": "Web content extraction not implemented yet. Integrate Firecrawl here."
        }
