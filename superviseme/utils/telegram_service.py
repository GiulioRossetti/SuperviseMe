"""
Telegram notification service for SuperviseMe
Handles sending notifications via Telegram bot
"""

import json
import logging
import time
from typing import Dict, List, Optional, Union

import telebot
from flask import current_app
from telebot.apihelper import ApiTelegramException

from superviseme.models import TelegramBotConfig, User_mgmt
from superviseme import db

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for managing Telegram bot notifications"""
    
    def __init__(self):
        self.bot = None
        self._config = None
    
    def _get_config(self) -> Optional[TelegramBotConfig]:
        """Get active Telegram bot configuration"""
        if not self._config:
            self._config = TelegramBotConfig.query.filter_by(is_active=True).first()
        return self._config
    
    def _get_bot(self) -> Optional[telebot.TeleBot]:
        """Get Telegram bot instance"""
        config = self._get_config()
        if not config:
            return None
        
        if not self.bot:
            try:
                self.bot = telebot.TeleBot(config.bot_token)
                # Test bot connection
                self.bot.get_me()
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                return None
        
        return self.bot
    
    def test_bot_connection(self) -> Dict[str, Union[bool, str]]:
        """Test Telegram bot connection and return status"""
        try:
            bot = self._get_bot()
            if not bot:
                return {
                    'success': False,
                    'message': 'No active Telegram bot configuration found'
                }
            
            bot_info = bot.get_me()
            return {
                'success': True,
                'message': f'Successfully connected to bot @{bot_info.username}',
                'bot_info': {
                    'id': bot_info.id,
                    'username': bot_info.username,
                    'first_name': bot_info.first_name
                }
            }
        except Exception as e:
            logger.error(f"Telegram bot connection test failed: {e}")
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }
    
    def send_notification(
        self, 
        user_id: int, 
        notification_type: str, 
        title: str, 
        message: str, 
        action_url: Optional[str] = None
    ) -> Dict[str, Union[bool, str]]:
        """
        Send a Telegram notification to a user
        
        Args:
            user_id: SuperviseMe user ID
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            action_url: Optional URL for action button
        
        Returns:
            Dict with success status and message
        """
        try:
            # Get user's Telegram configuration
            user = User_mgmt.query.get(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            if not user.telegram_enabled or not user.telegram_user_id:
                return {'success': False, 'message': 'Telegram notifications not enabled for user'}
            
            # Check if user wants this type of notification
            if user.telegram_notification_types:
                enabled_types = json.loads(user.telegram_notification_types)
                if notification_type not in enabled_types:
                    return {'success': False, 'message': f'Notification type {notification_type} not enabled for user'}
            
            # Get bot instance
            bot = self._get_bot()
            if not bot:
                return {'success': False, 'message': 'Telegram bot not configured'}
            
            # Format message
            telegram_message = self._format_message(title, message, action_url)
            
            # Send message
            bot.send_message(
                chat_id=user.telegram_user_id,
                text=telegram_message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info(f"Telegram notification sent to user {user_id} ({notification_type})")
            return {'success': True, 'message': 'Notification sent successfully'}
            
        except ApiTelegramException as e:
            logger.error(f"Telegram API error sending notification to user {user_id}: {e}")
            return {'success': False, 'message': f'Telegram API error: {str(e)}'}
        except Exception as e:
            logger.error(f"Error sending Telegram notification to user {user_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def _format_message(self, title: str, message: str, action_url: Optional[str] = None) -> str:
        """Format notification message for Telegram"""
        formatted_message = f"<b>🔔 {title}</b>\n\n{message}"
        
        if action_url and action_url != '#':
            # Build full URL if it's a relative path
            if action_url.startswith('/'):
                base_url = current_app.config.get('BASE_URL', 'https://superviseme.local')
                action_url = f"{base_url}{action_url}"
            formatted_message += f"\n\n<a href='{action_url}'>🔗 View Details</a>"
        
        formatted_message += "\n\n<i>📚 SuperviseMe</i>"
        return formatted_message
    
    def verify_user_chat(self, telegram_user_id: str) -> Dict[str, Union[bool, str, Dict]]:
        """
        Verify that a user chat is accessible by the bot
        
        Args:
            telegram_user_id: Telegram user ID or username
        
        Returns:
            Dict with verification result
        """
        try:
            bot = self._get_bot()
            if not bot:
                return {'success': False, 'message': 'Telegram bot not configured'}
            
            # Try to get chat info
            chat = bot.get_chat(telegram_user_id)
            
            return {
                'success': True,
                'message': 'Chat verified successfully',
                'chat_info': {
                    'id': chat.id,
                    'type': chat.type,
                    'username': getattr(chat, 'username', None),
                    'first_name': getattr(chat, 'first_name', None),
                    'last_name': getattr(chat, 'last_name', None)
                }
            }
            
        except ApiTelegramException as e:
            if 'chat not found' in str(e).lower():
                return {
                    'success': False,
                    'message': 'Chat not found. Please make sure you have started a conversation with the bot.'
                }
            else:
                return {'success': False, 'message': f'Telegram API error: {str(e)}'}
        except Exception as e:
            logger.error(f"Error verifying Telegram chat {telegram_user_id}: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
    
    def get_bot_info(self) -> Optional[Dict]:
        """Get information about the configured bot"""
        try:
            bot = self._get_bot()
            if not bot:
                return None
            
            bot_info = bot.get_me()
            return {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name,
                'can_join_groups': getattr(bot_info, 'can_join_groups', False),
                'can_read_all_group_messages': getattr(bot_info, 'can_read_all_group_messages', False),
                'supports_inline_queries': getattr(bot_info, 'supports_inline_queries', False)
            }
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None


# Singleton instance
_telegram_service = TelegramService()


def get_telegram_service() -> TelegramService:
    """Get singleton Telegram service instance"""
    return _telegram_service


def send_telegram_notification(user_id: int, notification_type: str, title: str, message: str, action_url: Optional[str] = None) -> bool:
    """
    Convenience function to send Telegram notification
    
    Returns:
        bool: True if notification was sent successfully
    """
    service = get_telegram_service()
    result = service.send_notification(user_id, notification_type, title, message, action_url)
    return result['success']


# Notification type definitions
NOTIFICATION_TYPES = {
    'new_update': {
        'name': 'New Thesis Update',
        'description': 'When a student posts a new thesis update',
        'icon': '📝'
    },
    'new_feedback': {
        'name': 'New Supervisor Feedback',
        'description': 'When a supervisor provides feedback on your thesis',
        'icon': '💬'
    },
    'todo_assigned': {
        'name': 'Task Assignment',
        'description': 'When a new task is assigned to you',
        'icon': '✅'
    },
    'todo_completed': {
        'name': 'Task Completion',
        'description': 'When a task assigned by you is completed',
        'icon': '🎯'
    },
    'thesis_status_change': {
        'name': 'Thesis Status Change',
        'description': 'When your thesis status is updated',
        'icon': '📊'
    },
    'deadline_reminder': {
        'name': 'Deadline Reminder',
        'description': 'Reminders for upcoming deadlines',
        'icon': '⏰'
    },
    'weekly_summary': {
        'name': 'Weekly Summary',
        'description': 'Weekly summary of thesis activities',
        'icon': '📈'
    }
}


def get_notification_types() -> Dict[str, Dict]:
    """Get available notification types"""
    return NOTIFICATION_TYPES


def get_default_notification_types() -> List[str]:
    """Get default enabled notification types for new users"""
    return ['new_update', 'new_feedback', 'todo_assigned', 'thesis_status_change']