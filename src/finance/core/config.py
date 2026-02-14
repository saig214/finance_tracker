
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App
    DEBUG: bool = False
    
    # Data Paths
    # Default to a 'data' folder in the project root if not specified
    DATA_DIR: Path = Path("data")
    
    @property
    def DB_DIR(self) -> Path:
        return self.DATA_DIR / "db"
        
    @property
    def RAW_DIR(self) -> Path:
        return self.DATA_DIR / "raw"
        
    @property
    def IMPORTS_DIR(self) -> Path:
        return self.DATA_DIR / "imports"

    @property
    def PROFILES_DIR(self) -> Path:
        return self.DATA_DIR / "profiles"

    @property
    def DATABASE_URL(self) -> str:
        # Ensure db directory exists
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.DB_DIR}/finance.db"

    # Bank/PDF Passwords
    HDFC_PDF_PASSWORD: str | None = None
    HDFC_CC_PASSWORD: str | None = None
    HDFC_BANK_PASSWORD: str | None = None
    ICICI_PDF_PASSWORD: str | None = None
    ICICI_CC_PASSWORD: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
