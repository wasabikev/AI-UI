# api/v1/websites.py

from quart import Blueprint, request, jsonify
from quart_auth import current_user
from auth import login_required

def create_websites_blueprint(
    get_session,
    select,
    Website,
    web_scraper_orchestrator,
    logger
):
    bp = Blueprint('websites', __name__, url_prefix='/api/v1/websites')

    @bp.route('/<int:website_id>', methods=['GET'])
    @login_required
    async def get_website(website_id):
        logger.debug(f"Attempting to fetch website with ID: {website_id}")
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(Website).filter_by(id=website_id)
                )
                website = result.scalar_one_or_none()
                if not website:
                    logger.warning(f"No website found with ID: {website_id}")
                    return jsonify({'error': 'Website not found'}), 404
                logger.debug(f"Website data: {website.to_dict()}")
                return jsonify({'website': website.to_dict()}), 200
        except Exception as e:
            logger.error(f"Exception occurred: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/scrape', methods=['POST'])
    @login_required
    async def scrape():
        # Placeholder for future integration with Firecrawl or similar AI-powered extractor
        return jsonify({
            "success": False,
            "message": "Web scraping is not currently implemented. Future versions will support AI-powered content extraction."
        }), 501

    @bp.route('/list/<int:system_message_id>', methods=['GET'])
    @login_required
    async def get_websites(system_message_id):
        async with get_session() as session:
            result = await session.execute(
                select(Website).filter_by(system_message_id=system_message_id)
            )
            websites = result.scalars().all()
            return jsonify({'websites': [website.to_dict() for website in websites]}), 200

    @bp.route('/add', methods=['POST'])
    @login_required
    async def add_website():
        data = await request.get_json()
        url = data.get('url')
        system_message_id = data.get('system_message_id')
        result, status = await web_scraper_orchestrator.add_website(url, system_message_id, current_user)
        return jsonify(result), status

    @bp.route('/remove/<int:website_id>', methods=['DELETE'])
    @login_required
    async def remove_website(website_id):
        result, status = await web_scraper_orchestrator.remove_website(website_id, current_user)
        return jsonify(result), status

    return bp
