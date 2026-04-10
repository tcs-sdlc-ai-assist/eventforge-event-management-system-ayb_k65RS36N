from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    display_name: str
    password: str
    confirm_password: str
    role: str = "Viewer"

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return v.strip()

    @field_validator("display_name")
    @classmethod
    def display_name_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 1:
            raise ValueError("Display name cannot be empty")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        valid_roles = ["Super Admin", "Admin", "Project Manager", "Developer", "QA", "Viewer"]
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserLogin(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Password cannot be empty")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserInDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool
    hashed_password: str
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("display_name")
    @classmethod
    def display_name_not_empty_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) < 1:
            raise ValueError("Display name cannot be empty")
        return v.strip() if v is not None else v

    @field_validator("role")
    @classmethod
    def role_must_be_valid_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_roles = ["Super Admin", "Admin", "Project Manager", "Developer", "QA", "Viewer"]
            if v not in valid_roles:
                raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v