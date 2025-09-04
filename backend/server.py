from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Set
import os
import logging
import uuid
import base64
import json
from pathlib import Path
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT and password settings
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, str] = {}  # user_id -> connection_id

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        self.user_connections[user_id] = connection_id
        return connection_id

    def disconnect(self, connection_id: str, user_id: str):
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if user_id in self.user_connections:
            del self.user_connections[user_id]

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.user_connections:
            connection_id = self.user_connections[user_id]
            if connection_id in self.active_connections:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(message)

    async def broadcast_to_chat(self, message: str, chat_id: str, sender_user_id: str):
        # Get all users in this chat
        chat = await db.chats.find_one({"id": chat_id})
        if chat:
            for user_id in chat.get("participants", []):
                if user_id != sender_user_id:  # Don't send to sender
                    await self.send_personal_message(message, user_id)

manager = ConnectionManager()

# Pydantic Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class Chat(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    is_group: bool = False
    participants: List[str] = []
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: Optional[datetime] = None

class ChatCreate(BaseModel):
    name: Optional[str] = None
    is_group: bool = False
    participants: List[str] = []

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_id: str
    sender_id: str
    sender_username: str
    content: str
    message_type: str = "text"  # text, image, file
    file_data: Optional[str] = None  # base64 encoded file data
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MessageCreate(BaseModel):
    chat_id: str
    content: str
    message_type: str = "text"
    file_data: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None

# Utility functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise credentials_exception
    return User(**user)

# Authentication routes
@api_router.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"$or": [{"username": user_data.username}, {"email": user_data.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email
    )
    
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    
    await db.users.insert_one(user_dict)
    
    # Create token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token, token_type="bearer", user=user)

@api_router.post("/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    user = await db.users.find_one({"username": user_data.username})
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    user_obj = User(**user)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_obj.id}, expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token, token_type="bearer", user=user_obj)

# User routes
@api_router.get("/users/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

@api_router.get("/users/search")
async def search_users(q: str, current_user: User = Depends(get_current_user)):
    users = await db.users.find(
        {"username": {"$regex": q, "$options": "i"}, "id": {"$ne": current_user.id}}
    ).to_list(10)
    return [{"id": user["id"], "username": user["username"]} for user in users]

# Chat routes
@api_router.post("/chats", response_model=Chat)
async def create_chat(chat_data: ChatCreate, current_user: User = Depends(get_current_user)):
    # Validate participants exist
    if chat_data.participants:
        participant_count = await db.users.count_documents({"id": {"$in": chat_data.participants}})
        if participant_count != len(chat_data.participants):
            raise HTTPException(status_code=400, detail="Some participants not found")
    
    # Add current user to participants
    participants = list(set([current_user.id] + chat_data.participants))
    
    # For private chats, ensure only 2 participants
    if not chat_data.is_group and len(participants) != 2:
        raise HTTPException(status_code=400, detail="Private chat must have exactly 2 participants")
    
    # Check if private chat already exists
    if not chat_data.is_group:
        existing_chat = await db.chats.find_one({
            "is_group": False,
            "participants": {"$all": participants, "$size": 2}
        })
        if existing_chat:
            return Chat(**existing_chat)
    
    chat = Chat(
        name=chat_data.name,
        is_group=chat_data.is_group,
        participants=participants,
        created_by=current_user.id
    )
    
    await db.chats.insert_one(chat.dict())
    return chat

@api_router.get("/chats", response_model=List[Chat])
async def get_user_chats(current_user: User = Depends(get_current_user)):
    chats = await db.chats.find(
        {"participants": current_user.id}
    ).sort("last_message_at", -1).to_list(100)
    
    # Add participant names for display
    result = []
    for chat in chats:
        chat_obj = Chat(**chat)
        if not chat_obj.is_group and not chat_obj.name:
            # Get other participant's name for private chats
            other_participant_id = next(p for p in chat_obj.participants if p != current_user.id)
            other_user = await db.users.find_one({"id": other_participant_id})
            if other_user:
                chat_obj.name = other_user["username"]
        result.append(chat_obj)
    
    return result

# Message routes
@api_router.post("/messages", response_model=Message)
async def send_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    # Verify user is in chat
    chat = await db.chats.find_one({"id": message_data.chat_id, "participants": current_user.id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    message = Message(
        chat_id=message_data.chat_id,
        sender_id=current_user.id,
        sender_username=current_user.username,
        content=message_data.content,
        message_type=message_data.message_type,
        file_data=message_data.file_data,
        file_name=message_data.file_name,
        file_type=message_data.file_type
    )
    
    await db.messages.insert_one(message.dict())
    
    # Update chat's last message time
    await db.chats.update_one(
        {"id": message_data.chat_id},
        {"$set": {"last_message_at": message.created_at}}
    )
    
    # Send to WebSocket connections
    message_json = json.dumps({
        "type": "new_message",
        "message": message.dict(),
        "chat_id": message_data.chat_id
    }, default=str)
    
    await manager.broadcast_to_chat(message_json, message_data.chat_id, current_user.id)
    
    return message

@api_router.get("/messages/{chat_id}", response_model=List[Message])
async def get_chat_messages(chat_id: str, skip: int = 0, limit: int = 50, current_user: User = Depends(get_current_user)):
    # Verify user is in chat
    chat = await db.chats.find_one({"id": chat_id, "participants": current_user.id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = await db.messages.find(
        {"chat_id": chat_id}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    messages.reverse()  # Show oldest first
    return [Message(**msg) for msg in messages]

# File upload route
@api_router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # Read file content
    content = await file.read()
    
    # Convert to base64
    file_data = base64.b64encode(content).decode('utf-8')
    
    return {
        "file_data": file_data,
        "file_name": file.filename,
        "file_type": file.content_type,
        "size": len(content)
    }

# WebSocket endpoint
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    connection_id = await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong or other WebSocket messages if needed
    except WebSocketDisconnect:
        manager.disconnect(connection_id, user_id)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()