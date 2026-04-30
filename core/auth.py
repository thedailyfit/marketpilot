"""
Authentication System
User registration, login, and JWT token management.
"""
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from dataclasses import dataclass, asdict
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


@dataclass
class User:
    """User model."""
    id: str
    email: str
    password_hash: str
    name: str
    created_at: str
    last_login: Optional[str] = None
    is_active: bool = True
    role: str = "trader"  # trader, admin


@dataclass
class Session:
    """User session."""
    token: str
    user_id: str
    created_at: str
    expires_at: str
    ip_address: Optional[str] = None


class AuthManager:
    """
    Handles user authentication with file-based storage.
    For production, use a proper database like PostgreSQL.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.users_file = self.data_dir / "users.json"
        self.sessions_file = self.data_dir / "sessions.json"
        
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Session] = {}
        
        self._load_data()
    
    def _load_data(self):
        """Load users and sessions from files."""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    self.users = {
                        uid: User(**user_data) 
                        for uid, user_data in data.items()
                    }
            except Exception as e:
                logger.error(f"Failed to load users: {e}")
        
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    self.sessions = {
                        token: Session(**session_data)
                        for token, session_data in data.items()
                    }
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
    
    def _save_users(self):
        """Save users to file."""
        with open(self.users_file, 'w') as f:
            data = {uid: asdict(user) for uid, user in self.users.items()}
            json.dump(data, f, indent=2)
    
    def _save_sessions(self):
        """Save sessions to file."""
        with open(self.sessions_file, 'w') as f:
            data = {token: asdict(session) for token, session in self.sessions.items()}
            json.dump(data, f, indent=2)
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt."""
        salt = "marketpilot_salt_2024"
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)
    
    def _generate_user_id(self) -> str:
        """Generate a unique user ID."""
        return f"user_{secrets.token_hex(8)}"
    
    def register(
        self, 
        email: str, 
        password: str, 
        name: str = ""
    ) -> Dict:
        """
        Register a new user.
        
        Returns:
            Dict with success status and user info or error
        """
        # Validate email
        if not email or "@" not in email:
            return {"success": False, "error": "Invalid email address"}
        
        email = email.lower().strip()
        
        # Check if email exists
        for user in self.users.values():
            if user.email == email:
                return {"success": False, "error": "Email already registered"}
        
        # Validate password
        if len(password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters"}
        
        # Create user
        user_id = self._generate_user_id()
        user = User(
            id=user_id,
            email=email,
            password_hash=self._hash_password(password),
            name=name or email.split("@")[0],
            created_at=datetime.now().isoformat()
        )
        
        self.users[user_id] = user
        self._save_users()
        
        logger.info(f"New user registered: {email}")
        
        # Auto-login after registration
        return self.login(email, password)
    
    def login(
        self, 
        email: str, 
        password: str,
        ip_address: str = None
    ) -> Dict:
        """
        Login user and create session.
        
        Returns:
            Dict with token and user info or error
        """
        email = email.lower().strip()
        password_hash = self._hash_password(password)
        
        # Find user
        user = None
        for u in self.users.values():
            if u.email == email:
                user = u
                break
        
        if not user:
            return {"success": False, "error": "Invalid email or password"}
        
        if user.password_hash != password_hash:
            return {"success": False, "error": "Invalid email or password"}
        
        if not user.is_active:
            return {"success": False, "error": "Account is disabled"}
        
        # Create session
        token = self._generate_token()
        session = Session(
            token=token,
            user_id=user.id,
            created_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(days=7)).isoformat(),
            ip_address=ip_address
        )
        
        self.sessions[token] = session
        self._save_sessions()
        
        # Update last login
        user.last_login = datetime.now().isoformat()
        self._save_users()
        
        logger.info(f"User logged in: {email}")
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role
            }
        }
    
    def validate_token(self, token: str) -> Optional[User]:
        """
        Validate session token and return user.
        
        Returns:
            User object if valid, None otherwise
        """
        if not token:
            return None
        
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        session = self.sessions.get(token)
        if not session:
            return None
        
        # Check expiry
        expires = datetime.fromisoformat(session.expires_at)
        if datetime.now() > expires:
            # Session expired, clean up
            del self.sessions[token]
            self._save_sessions()
            return None
        
        # Get user
        user = self.users.get(session.user_id)
        if not user or not user.is_active:
            return None
        
        return user
    
    def logout(self, token: str) -> Dict:
        """
        Logout user by invalidating session.
        """
        if token.startswith("Bearer "):
            token = token[7:]
        
        if token in self.sessions:
            del self.sessions[token]
            self._save_sessions()
            return {"success": True, "message": "Logged out successfully"}
        
        return {"success": False, "error": "Invalid session"}
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user info (without password)."""
        user = self.users.get(user_id)
        if not user:
            return None
        
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at,
            "last_login": user.last_login
        }
    
    def update_user(self, user_id: str, updates: Dict) -> Dict:
        """Update user profile."""
        user = self.users.get(user_id)
        if not user:
            return {"success": False, "error": "User not found"}
        
        if "name" in updates:
            user.name = updates["name"]
        
        if "password" in updates:
            if len(updates["password"]) < 6:
                return {"success": False, "error": "Password must be at least 6 characters"}
            user.password_hash = self._hash_password(updates["password"])
        
        self._save_users()
        return {"success": True, "message": "Profile updated"}
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        now = datetime.now()
        expired = [
            token for token, session in self.sessions.items()
            if datetime.fromisoformat(session.expires_at) < now
        ]
        
        for token in expired:
            del self.sessions[token]
        
        if expired:
            self._save_sessions()
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global instance
auth_manager = AuthManager()
