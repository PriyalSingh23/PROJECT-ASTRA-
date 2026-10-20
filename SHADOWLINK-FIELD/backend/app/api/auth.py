from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db, utcnow
from app.core.security import verify_password, create_access_token, get_current_user
from app.models.user import User
from app.schemas.auth import Token, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled")

    user.last_login_at = utcnow()
    db.commit()

    token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.user_id}
    )
    return Token(access_token=token, token_type="bearer", role=user.role, username=user.username)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
