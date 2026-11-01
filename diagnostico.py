import os, re, socket, time
import oracledb
from dotenv import load_dotenv

load_dotenv()
wd = os.environ["WALLET_DIR"]
texto = open(os.path.join(wd, "tnsnames.ora"), encoding="utf-8").read()
host = re.search(r"host=([^)\s]+)", texto, re.I).group(1)
port = int(re.search(r"port=(\d+)", texto, re.I).group(1))
print("Host:", host, "| Puerto:", port)

for fam, tipo, proto, _, sa in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
    t = time.time()
    s = socket.socket(fam, tipo, proto)
    s.settimeout(10)
    try:
        s.connect(sa)
        print("Socket simple", sa[0], "OK en", round(time.time() - t, 1), "s")
    except Exception as e:
        print("Socket simple", sa[0], "FALLA:", e)
    finally:
        s.close()

t = time.time()
try:
    cnx = oracledb.connect(
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        dsn=os.environ["DB_DSN"], config_dir=wd, wallet_location=wd,
        wallet_password=os.environ["WALLET_PASSWORD"],
        tcp_connect_timeout=15, retry_count=0)
    print("oracledb: CONECTADO como", cnx.username)
    cnx.close()
except Exception as e:
    print("oracledb FALLA tras", round(time.time() - t, 1), "s:", str(e).splitlines()[-1])