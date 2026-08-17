import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "db"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "anima"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)
cur = conn.cursor(dictionary=True)
cur.execute("SELECT NOW() as db_now, UTC_TIMESTAMP() as db_utc, @@global.time_zone as global_tz, @@session.time_zone as session_tz, @@system_time_zone as sys_tz")
res = cur.fetchone()
print("DB Time Results:", res)
cur.close()
conn.close()
