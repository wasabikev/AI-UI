# time_utils.py

import re
import datetime
import pytz
import uuid
import platform
from quart import current_app as app

async def generate_time_context(user=None):
    """
    Generate time context information for the AI.
    Returns a string with current date, time, and day of week.
    
    Args:
        user: User object or dictionary with timezone information
    
    Returns:
        str: Formatted time context information
    """
    try:
        # Extract timezone from user object or dictionary
        if user is None:
            timezone_str = 'UTC'
        elif isinstance(user, dict) and 'timezone' in user:
            timezone_str = user['timezone']
        elif hasattr(user, 'timezone') and user.timezone:
            timezone_str = user.timezone
        else:
            timezone_str = 'UTC'
            
        app.logger.debug(f"Using timezone: {timezone_str}")
            
        try:
            tz = pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            app.logger.warning(f"Unknown timezone: {timezone_str}, falling back to UTC")
            tz = pytz.UTC
            
        now = datetime.datetime.now(tz)
        
        # Format the date and time with 12-hour clock format
        formatted_date = now.strftime('%A, %B %d, %Y')
        
        # Use platform-specific format to remove leading zero in hour
        if platform.system() == 'Windows':
            formatted_time = now.strftime('%#I:%M %p')  # Windows format
        else:
            formatted_time = now.strftime('%-I:%M %p')  # Unix format
        
        # Create the time context message
        time_context = (
            f"Current date and time: {formatted_date}, {formatted_time} {tz.zone}. "
            f"Please use this information when responding to time-sensitive queries, "
            f"while acknowledging that your training data has a cutoff date."
        )
        
        # Add season information
        month = now.month
        day = now.day
        
        if (month == 12 and day >= 21) or (month <= 2) or (month == 3 and day < 20):
            season = "winter"
        elif (month == 3 and day >= 20) or (month <= 5) or (month == 6 and day < 21):
            season = "spring"
        elif (month == 6 and day >= 21) or (month <= 8) or (month == 9 and day < 22):
            season = "summer"
        else:
            season = "autumn"
            
        time_context += f" It is currently {season} in the northern hemisphere."
        
        # Check for major holidays (simplified example)
        holidays = []
        if month == 12 and day >= 24 and day <= 26:
            holidays.append("Christmas")
        elif month == 1 and day == 1:
            holidays.append("New Year's Day")
        elif month == 7 and day == 4:
            holidays.append("Independence Day (US)")
        
        if holidays:
            time_context += f" Notable current holidays: {', '.join(holidays)}."
        
        # Log debug information without including it in the time context
        app.logger.debug(f"Generated time context: {time_context}")
        return time_context
        
    except Exception as e:
        app.logger.error(f"Error generating time context: {str(e)}")
        # Return a simplified fallback time context
        return f"Current date: {datetime.datetime.now(pytz.UTC).strftime('%Y-%m-%d')} UTC."

async def clean_and_update_time_context(messages, user, enable_time_sense, logger=None):
    print("===== ENTERING clean_and_update_time_context =====")
    print(f"Enable time sense: {enable_time_sense}")
    """
    Cleans any existing time context and adds a fresh one if enabled.
    
    Args:
        messages: List of message dictionaries
        user: User object for timezone information
        enable_time_sense: Boolean indicating if time sense is enabled
        logger: Optional logger for debugging
        
    Returns:
        List of updated messages
    """
    # Make a copy of messages to avoid modifying the original
    updated_messages = messages.copy()
    
    # Find the system message
    system_idx = None
    for i, msg in enumerate(updated_messages):
        if msg['role'] == 'system':
            system_idx = i
            break
    
    # If no system message found, create one
    if system_idx is None:
        system_message = {"role": "system", "content": ""}
        updated_messages.insert(0, system_message)
        system_idx = 0
        if logger:
            logger.info("No system message found, created a new one")
    
    # Get the current system message content
    system_content = updated_messages[system_idx]['content']
    
    # Always clean existing time context regardless of whether it's enabled
    if '<Time Context>' in system_content:
        if logger:
            logger.info("Found existing time context, cleaning it")
        
        # Use regex to remove everything between and including <Time Context> and </Time Context> tags
        cleaned_content = re.sub(r'<Time Context>[\s\S]*?</Time Context>', '', system_content)
        
        # Remove any extra blank lines that might have been created
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
        
        # Update the system message with cleaned content
        updated_messages[system_idx]['content'] = cleaned_content.strip()
        
        if logger:
            logger.debug(f"Cleaned system message: {updated_messages[system_idx]['content'][:100]}...")
    
    # Add fresh time context if enabled
    if enable_time_sense:
        if logger:
            logger.info("Time sense enabled, adding fresh time context")
        
        # Generate new time context
        time_context = await generate_time_context(user)
        
        # Add the new time context to the cleaned system message
        updated_messages[system_idx]['content'] = (
            f"{updated_messages[system_idx]['content'].strip()}\n\n"
            f"<Time Context>\n{time_context}\n</Time Context>"
        )
        
        if logger:
            logger.debug(f"Updated system message with time context: {updated_messages[system_idx]['content'][:100]}...")

    print("===== EXITING clean_and_update_time_context =====")
    return updated_messages