# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Optional
from config import Config
from data.user import BotDB
from utils.videoclient import VideoClient


if TYPE_CHECKING:
    from bot.bot import Bot
    
class Dependencies:
    
    def __init__(self):
        self.config = Config()
        
        self.db = BotDB(self.config.MONGO_URI, "video_encoder")
        
        # self.user_manager = UserManager(self.mongo)  
        self.videoclient = VideoClient("test", out_pth="data_encode", trd=100)  
        self.videoclient.start()
        
        self.bot: Optional['Bot'] = None
    
    def initialize_bot(self) -> 'Bot':
        from bot.bot import Bot  
        
        self.bot = Bot(
            mongo=self.db,
            config=self.config,
            videoclient=self.videoclient,
            # usermanager=self.user_manager,
            session_name=self.config.SESSION_NAME
        )
        return self.bot
    
    async def startup(self):
        await self.db.connect()
        
    
    async def shutdown(self):
        """Nettoie les ressources."""
        if self.bot:
            await self.bot.stop()
        await self.db.disconnect()
        self.videoclient.stop()