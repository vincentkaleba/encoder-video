from dataclasses import dataclass, field
from enum import Enum, auto
import logging
from typing import Optional, Dict, List, Any
import datetime
import hashlib
import json
import motor.motor_asyncio
from pymongo import DESCENDING, ASCENDING
from pymongo.errors import PyMongoError
from bson import ObjectId
log = logging.getLogger(__name__)
from motor.core import AgnosticClient, AgnosticDatabase, AgnosticCollection

class Sex(Enum):
    """Genre de l'utilisateur"""
    M, F, N = "M", "F", "N" 

class SubType(Enum):
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    PREM = "PREM"

class TaskStatus(Enum):
    """Statuts possibles d'une tâche"""
    PEND, PROC, COMP, FAIL = "pend", "proc", "comp", "fail"  # En attente, En cours, Terminé, Échec

class TaskType(Enum):
    COMPRESS = "compress"
    CUT = "cut"
    CONVERT = "convert"

    VIDEO_MERGE = "video_merge"
    VIDEO_SPLIT = "video_split"
    VIDEO_TRIM = "video_trim"
    GENERATE_THUMBNAIL = "generate_thumbnail"

    AUDIO_EXTRACT = "audio_extract"
    AUDIO_SELECTION = "audio_selection"
    CONVERT_AUDIO = "convert_audio"
    REMOVE_AUDIO = "remove_audio"
    MERGE_VIDEO_AUDIO = "merge_video_audio"

    SUBTITLE_ADD = "subtitle_add"
    SUBTITLE_EXTRACT = "subtitle_extract"
    CHOOSE_SUBTITLE = "choose_subtitle"
    REMOVE_SUBTITLES = "remove_subtitles"
    CHOOSE_SUBTITLE_BURN = "choose_subtitle_burn"
    FORCE_SUBTITLE = "force_subtitle"

    ADD_CHAPTERS = "add_chapters"
    EDIT_CHAPTER = "edit_chapter"
    SPLIT_CHAPTER = "split_chapter"
    REMOVE_CHAPTERS = "remove_chapters"
    GET_CHAPTERS = "get_chapters"
    GET_CHAPTER = "get_chapter"

    UNKN = "unkn"

SUB_CONFIG = {
    SubType.FREE: {"pts": 1, "files": 3, "price": 0},
    SubType.BASIC: {"pts": 5, "files": 10, "price": 4.99},
    SubType.PRO: {"pts": 20, "files": 30, "price": 14.99},
    SubType.PREM: {"pts": 50, "files": 100, "price": 29.99}
}

@dataclass
class Task:
    """Représente une tâche de traitement de fichier"""
    fid: str   
    uid: int
    qry: Dict[str, Any]       
    qh: str = field(init=False)
    tms: datetime.datetime = field(default_factory=datetime.datetime.now) 
    pts: int = 0               
    typ: str = TaskType.UNKN.value 
    sts: str = TaskStatus.PEND.value
    res: List[str] = field(default_factory=list)
    tg: List[str] = field(default_factory=list)
    _id: Optional[Any] = field(default=None)


    def __post_init__(self):
        """Calcule automatiquement le hash de la requête"""
        self.qh = hashlib.md5(json.dumps(self.qry, sort_keys=True).encode()).hexdigest()
        self.typ = self.qry.get('action', TaskType.UNKN.value)
    
@dataclass
class DailyUsage:
    dt: datetime.date = field(default_factory=lambda: datetime.date.today())  
    pts: int = 0
    fls: int = 0
    tks: List[Dict] = field(default_factory=list)

    def to_mongo_dict(self):
        """Convertit l'objet en dictionnaire compatible MongoDB"""
        return {
            "dt": datetime.datetime.combine(self.dt, datetime.time.min),
            "pts": self.pts,
            "fls": self.fls,
            "tks": self.tks
        }

@dataclass
class User:
    """Profil utilisateur du bot"""
    uid: int                   # ID utilisateur
    fn: str                    # Prénom
    ln: str = ""               # Nom de famille
    un: str = ""               # Nom d'utilisateur
    sx: Sex = Sex.N            # Genre
    reg: datetime.datetime = field(default_factory=datetime.datetime.now)
    lst: datetime.datetime = field(default_factory=datetime.datetime.now)
    sub: SubType = SubType.FREE # Abonnement
    exp: Optional[datetime.datetime] = None # Expiration abonnement
    tpts: int = 0              # Points totaux
    cfg: Dict = field(default_factory=dict) # Configuration
    usg: List[DailyUsage] = field(default_factory=list) # Historique usage
    _id: str = ""              # ID MongoDB

    def __post_init__(self):
        if not self.cfg:
            self.cfg = {'lang': 'fr', 'qual': 'med', 'notif': True}

    def curr_usage(self) -> DailyUsage:
        """Retourne l'utilisation du jour (crée un suivi si absent)"""
        today = datetime.date.today()
        for u in self.usg:
            if u.dt == today:
                return u
        new_usage = DailyUsage()
        self.usg.append(new_usage)
        return new_usage

    def can_process(self, pts_needed=1) -> bool:
        """Vérifie si l'utilisateur peut traiter un fichier"""
        cfg = SUB_CONFIG[self.sub]
        usage = self.curr_usage()
        return (usage.pts + pts_needed <= cfg['pts']) and (usage.fls < cfg['files'])
    
    def to_mongo_dict(self):
        """Convertit l'objet User en dictionnaire compatible MongoDB"""
        return {
            "uid": self.uid,
            "fn": self.fn,
            "ln": self.ln,
            "un": self.un,
            "sx": self.sx.value,
            "reg": self.reg,
            "lst": self.lst,
            "sub": self.sub.value,
            "exp": self.exp,
            "tpts": self.tpts,
            "cfg": self.cfg,
            "usg": [u.to_mongo_dict() for u in self.usg],
            "_id": self._id if self._id else None
        }
    
    class Config:
        extra = "ignore"

class BotDB:
    """Interface de gestion de la base de données pour le bot"""
    
    def __init__(self, mongo_uri: str, db_name: str, max_pool: int = 100, min_pool: int = 10):
        """
        Initialise la connexion à MongoDB
        :param mongo_uri: URI de connexion MongoDB
        :param db_name: Nom de la base de données
        """
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.max_pool = max_pool
        self.min_pool = min_pool
        self._client: Optional[AgnosticClient] = None
        self._database: Optional[AgnosticDatabase] = None
        self._users: Optional[AgnosticCollection] = None
        self._tasks: Optional[AgnosticCollection] = None

    async def _ensure_indexes(self):
        """Crée les index optimaux pour les requêtes fréquentes"""
        await self._tasks.create_index([("uid", ASCENDING), ("fid", ASCENDING), ("qh", ASCENDING)])
        await self._tasks.create_index([("uid", ASCENDING), ("tms", DESCENDING)])
        await self._users.create_index([("uid", ASCENDING)])
    
    async def connect(self) -> None:
        """Établit la connexion à MongoDB"""
        if self._client is not None:
            return

        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(
                self.mongo_uri,
                maxPoolSize=self.max_pool,
                minPoolSize=self.min_pool,
                connectTimeoutMS=5000,
                serverSelectionTimeoutMS=5000
            )
            self._database = self._client[self.db_name]
            self._users = self._database["users"]
            self._tasks = self._database["tasks"]
            await self._client.admin.command('ping')
            await self._ensure_indexes()
            log.info(f"Connected to MongoDB database '{self.db_name}'")
        except PyMongoError as e:
            log.error(f"MongoDB connection failed: {e}")
            self._client = None
            self._database = None
            raise ConnectionError(f"Could not connect to MongoDB: {e}")

    async def disconnect(self) -> None:
        """Ferme la connexion à MongoDB"""
        if self._client is not None:
            try:
                self._client.close()
                log.info("MongoDB connection closed")
            except Exception as e:
                log.error(f"Error closing MongoDB connection: {e}")
            finally:
                self._client = None
                self._database = None
                self._users = None
                self._tasks = None

    async def is_connected(self) -> bool:
        """Vérifie si la connexion est active"""
        try:
            if self._client is None:
                return False
            await self._client.admin.command('ping')
            return True
        except PyMongoError:
            return False

    # Méthodes Utilisateurs
    async def get_user(self, uid: int) -> Optional[User]:
        """
        Récupère un utilisateur par son ID
        :param uid: ID utilisateur Telegram
        :return: Objet User ou None si non trouvé
        """
        if u := await self._users.find_one({"uid": uid}):
            return self._map_user(u)
        return None

    def _map_user(self, data: Dict) -> User:
        """Convertit les données MongoDB en objet User"""
        data['sx'] = Sex(data['sx'])
        data['sub'] = SubType(data['sub'])
        if 'usg' in data:
            data['usg'] = [DailyUsage(
                dt=u['dt'].date() if isinstance(u['dt'], datetime.datetime) else u['dt'],
                pts=u['pts'],
                fls=u['fls'],
                tks=u['tks']
            ) for u in data['usg']]
        return User(**data)

    async def save_user(self, user: User) -> bool:
        """
        Sauvegarde un utilisateur en base avec conversion correcte des types
        :param user: Objet User à sauvegarder
        :return: True si succès
        """
        try:
            data = user.to_mongo_dict()
            
            res = await self._users.update_one(
                {"uid": user.uid},
                {"$set": data},
                upsert=True
            )
            return res.acknowledged
            
        except Exception as e:
            log.error(f"Erreur save_user {user.uid}: {str(e)}")
            return False

    async def update_sub(self, uid: int, sub_type: SubType) -> bool:
        """
        Met à jour l'abonnement d'un utilisateur
        :param uid: ID utilisateur
        :param sub_type: Nouveau type d'abonnement
        :return: True si mis à jour
        """
        expiry = datetime.datetime.now() + datetime.timedelta(days=30)
        res = await self._users.update_one(
            {"uid": uid},
            {"$set": {
                "sub": sub_type.value,
                "exp": expiry,
                "tpts": SUB_CONFIG[sub_type]['pts'] * 30
            }}
        )
        return res.modified_count > 0

    # Méthodes Tâches
    async def create_task(self, uid: int, fid: str, qry: Dict) -> str:
        """
        Crée une nouvelle tâche en statut 'pending'
        :param uid: ID utilisateur
        :param fid: ID du fichier à traiter
        :param qry: Paramètres de traitement
        :return: ID de la tâche créée
        """
        task = Task(uid=uid, fid=fid, qry=qry)  
        task_data = {
            "uid": task.uid,
            "fid": task.fid,
            "qry": task.qry,
            "qh": task.qh,
            "tms": task.tms,
            "pts": task.pts,
            "typ": task.typ,
            "sts": task.sts,
            "res": task.res,
            "tg": task.tg
        }
        res = await self._tasks.insert_one(task_data)
        return str(res.inserted_id)

    async def update_task(self, tid: str, **updates) -> bool:
        """
        Met à jour une tâche existante
        :param tid: ID de la tâche
        :param updates: Champs à mettre à jour
        :return: True si modification effectuée
        """
        updates["tms"] = datetime.datetime.now()
        res = await self._tasks.update_one(
            {"_id": ObjectId(tid)},
            {"$set": updates}
        )
        return res.modified_count > 0

    async def find_existing(self, uid: int, qry: Dict) -> Optional[Task]:
        try:
            qh = hashlib.md5(
                json.dumps({
                    'file_type': str(qry.get('file_type', '')).strip().lower(),
                    'file_name': str(qry.get('file_name', '')).strip(),
                    'initial_msg': bool(qry.get('initial_msg', False)),
                    'points_cost': int(qry.get('points_cost', 1))
                }, sort_keys=True).encode()
            ).hexdigest()

            if doc := await self._tasks.find_one({
                "$or": [{"uid": uid}, {"uid": str(uid)}],
                "qh": qh,
                "sts": {"$ne": "fail"}
            }):
                return Task(
                    uid=doc['uid'],
                    fid=doc.get('fid', ''),
                    qry=doc.get('qry', {}),
                    _id=doc.get('_id')
                )
            return None
        except Exception as e:
            print(f"Erreur find_existing: {str(e)}")
            return None
    
    async def get_user_tasks(self, uid: int, limit: int = 10) -> List[Task]:
        """
        Récupère les tâches récentes d'un utilisateur
        :param uid: ID utilisateur
        :param limit: Nombre max de tâches à retourner
        :return: Liste des tâches
        """
        tasks = []
        async for t in self._tasks.find({"uid": uid}).sort("tms", DESCENDING).limit(limit):
            tasks.append(Task(**t))
        return tasks

    # Méthodes Combinées
    async def process_file(self, uid: int, fid: str, qry: Dict) -> Optional[Dict]:
        """
        Gère le workflow complet de traitement d'un fichier
        :param uid: ID utilisateur
        :param fid: ID du fichier
        :param qry: Paramètres de traitement
        :return: Dict avec status et infos supplémentaires
        """
        if existing := await self.find_existing(uid, qry):
            return {"status": "exists", "tg_files": existing.tg}
        
        user = await self.get_user(uid)
        if not user or not user.can_process():
            return {"status": "limit_reached"}
        
        tid = await self.create_task(uid, fid, qry)
        return {"status": "created", "task_id": tid}

    async def complete_task(self, tid: str, res: List[str], tg: List[str]) -> bool:
        """
        Finalise une tâche après traitement
        :param tid: ID de la tâche
        :param res: IDs des résultats
        :param tg: IDs Telegram des fichiers
        :return: True si mise à jour réussie
        """
        return await self.update_task(
            tid,
            sts=TaskStatus.COMP.value,
            res=res,
            tg=tg,
            pts=1
        )

    # Méthodes Admin
    async def get_daily_stats(self, date: datetime.date = None) -> Dict:
        """
        Génère des statistiques d'utilisation pour une date
        :param date: Date à analyser (aujourd'hui par défaut)
        :return: Dict avec statistiques par abonnement
        """
        date = date or datetime.date.today()
        pipeline = [
            {"$unwind": "$usg"},
            {"$match": {"usg.dt": datetime.datetime.combine(date, datetime.time.min)}},
            {"$group": {
                "_id": "$sub",
                "users": {"$sum": 1},
                "points": {"$sum": "$usg.pts"},
                "files": {"$sum": "$usg.fls"}
            }}
        ]
        stats = {}
        async for r in self._users.aggregate(pipeline):
            stats[r["_id"]] = r
        return stats

    async def renew_subs(self) -> Dict[str, int]:
        """
        Renouvelle automatiquement les abonnements expirés
        :return: Statistiques des renouvellements
        """
        now = datetime.datetime.now()
        res = {"total": 0, "renewed": 0, "downgraded": 0}
        
        async for u in self._users.find({
            "exp": {"$lt": now},
            "sub": {"$ne": "FREE"}
        }):
            res["total"] += 1
            user = self._map_user(u)
            
            if user.tpts >= SUB_CONFIG[user.sub]['price']:
                user.tpts -= SUB_CONFIG[user.sub]['price']
                user.exp = now + datetime.timedelta(days=30)
                res["renewed"] += 1
            else:
                user.sub = SubType.FREE
                user.exp = None
                res["downgraded"] += 1
                
            await self.save_user(user)
        
        return res