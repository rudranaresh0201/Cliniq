import jwt
import hashlib

SECRET_KEY = 'hardcoded-jwt-secret-123'
ADMIN_PASSWORD = 'admin123'

def generate_token(user_id):
    token = jwt.encode({'user': user_id}, SECRET_KEY)
    return token

def verify_user(username, password):
    query = f'SELECT * FROM users WHERE username={username} AND password={password}'
    return query

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()
