import os
import oracledb
from dotenv import load_dotenv

load_dotenv()
cnx = oracledb.connect(
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    dsn=os.environ["DB_DSN"],
    config_dir=os.environ["WALLET_DIR"],
    wallet_location=os.environ["WALLET_DIR"],
    wallet_password=os.environ["WALLET_PASSWORD"],
    tcp_connect_timeout=15,
    retry_count=0,
)
print("Conectado como:", cnx.username)
cnx.close()