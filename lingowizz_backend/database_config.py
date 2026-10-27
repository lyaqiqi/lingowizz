import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL 数据库连接配置：从环境变量 DATABASE_URL 读取
# 例：postgresql://username:password@host:5432/database?sslmode=require
DATABASE_URL = os.getenv('DATABASE_URL')

def get_database_connection():
    """获取数据库连接"""
    if not DATABASE_URL or not DATABASE_URL.startswith('postgresql'):
        print("未配置 PostgreSQL 的 DATABASE_URL（本地默认使用 SQLite，无需本脚本）")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except (Exception, psycopg2.Error) as error:
        print(f"连接数据库时出错: {error}")
        return None

def test_database_connection():
    """测试数据库连接"""
    try:
        conn = get_database_connection()
        if conn:
            cur = conn.cursor()
            print("成功连接到数据库！")

            # 查询 public 模式下的所有表
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)

            tables = cur.fetchall()
            print("数据库中的表 (public schema):")
            for table in tables:
                print(table[0])

            cur.close()
            conn.close()
            return True
    except (Exception, psycopg2.Error) as error:
        print(f"操作数据库时出错: {error}")
        return False

if __name__ == "__main__":
    test_database_connection()
