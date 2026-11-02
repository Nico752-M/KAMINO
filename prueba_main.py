import os, oracledb
d = os.path.abspath("Wallet")
print(d, os.listdir(d))
c = oracledb.connect(user="cea_web", password=input("clave cea_web: "),
                     dsn="kamino_low", config_dir=d, wallet_location=d,
                     wallet_password=input("clave wallet: "))
print("OK", c.version)