import os, oracledb
from config import Config

print("DSN:", Config.DB_DSN, "| USUARIO:", Config.DB_USER)
print("Wallet:", os.path.abspath(Config.WALLET_DIR), "| existe:", os.path.isdir(Config.WALLET_DIR))

args = dict(user=Config.DB_USER, password=Config.DB_PASSWORD, dsn=Config.DB_DSN,
            config_dir=Config.WALLET_DIR, wallet_location=Config.WALLET_DIR,
            wallet_password=Config.WALLET_PASSWORD)

try:
    c = oracledb.connect(**args)
    print("connect directo: OK")
    c.close()
except Exception as e:
    print("connect directo: FALLA ->", e)

try:
    p = oracledb.create_pool(min=1, max=2, **args)
    p.acquire().close()
    print("pool: OK")
except Exception as e:
    print("pool: FALLA ->", e)