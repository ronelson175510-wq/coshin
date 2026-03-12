# moved to backup_words_detector
# Coshin.com Flask Backend with MySQL
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import mysql.connector
import jwt
import bcrypt
import datetime
import base64
import io
import os
from functools import wraps
from dotenv import load_dotenv

try:
    from deepmultilingualpunctuation import PunctuationModel
    PUNCT_IMPORT_ERROR = None
except Exception as err:
    PunctuationModel = None
    PUNCT_IMPORT_ERROR = str(err)

try:
    import spacy
    NLP_IMPORT_ERROR = None
except Exception as err:
    spacy = None
    NLP_IMPORT_ERROR = str(err)

load_dotenv()

app = Flask(__name__)

# CORS configuration: allow all by default, or restrict via CORS_ORIGINS env var.
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins == '*':
    CORS(app)
else:
    allowed_origins = [origin.strip() for origin in cors_origins.split(',') if origin.strip()]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

# Configuration
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'change-this-secret-in-production')
app.config['JWT_EXPIRATION_HOURS'] = 24


def parse_bool_env(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def get_db_port():
    raw_port = os.getenv('DB_PORT', '3306')
    try:
        return int(raw_port)
    except ValueError:
        print(f"⚠️ Invalid DB_PORT '{raw_port}', falling back to 3306")
        return 3306


def build_db_config():
    config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': get_db_port(),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', 'coshin')
    }

    # Optional SSL settings for managed/remote MySQL databases.
    ssl_mode = (os.getenv('DB_SSL_MODE', 'disabled') or 'disabled').strip().lower()
    if ssl_mode in ('required', 'require', 'verify_ca', 'verify_identity'):
        config['ssl_disabled'] = False

        ssl_ca = os.getenv('DB_SSL_CA')
        ssl_cert = os.getenv('DB_SSL_CERT')
        ssl_key = os.getenv('DB_SSL_KEY')

        if ssl_ca:
            config['ssl_ca'] = ssl_ca
        if ssl_cert:
            config['ssl_cert'] = ssl_cert
        if ssl_key:
            config['ssl_key'] = ssl_key

        verify_cert = ssl_mode in ('verify_ca', 'verify_identity')
        verify_identity = ssl_mode == 'verify_identity'

        config['ssl_verify_cert'] = parse_bool_env(
            os.getenv('DB_SSL_VERIFY_CERT'),
            default=verify_cert
        )
        config['ssl_verify_identity'] = parse_bool_env(
            os.getenv('DB_SSL_VERIFY_IDENTITY'),
            default=verify_identity
        )

    return config


# MySQL Database Configuration
DB_CONFIG = build_db_config()
PUNCT_MODEL = None


def ensure_users_schema_columns():
    """Ensure optional users table columns exist for newer features."""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Could not verify users schema columns (no DB connection)")
        return

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'email_public'
            """,
            (DB_CONFIG['database'],)
        )
        exists = cursor.fetchone()['count'] > 0

        if not exists:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN email_public TINYINT(1) NOT NULL DEFAULT 0"
            )
            conn.commit()
            print("✅ Added users.email_public column")

        # Older schemas may store profile pictures in TEXT (64KB), which is too small for mobile photos.
        cursor.execute(
            """
            SELECT DATA_TYPE AS data_type
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'profile_picture'
            """,
            (DB_CONFIG['database'],)
        )
        profile_picture_col = cursor.fetchone()

        if profile_picture_col and profile_picture_col['data_type'].lower() != 'longtext':
            cursor.execute(
                "ALTER TABLE users MODIFY COLUMN profile_picture LONGTEXT"
            )
            conn.commit()
            print("✅ Updated users.profile_picture to LONGTEXT")
    except mysql.connector.Error as err:
        print(f"⚠️ Failed to ensure users schema columns: {err}")
    finally:
        cursor.close()
        conn.close()


def ensure_messages_schema():
    """Ensure messages table exists for user-to-user chat."""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Could not verify messages schema (no DB connection)")
        return

    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_sender (sender_id),
                INDEX idx_receiver (receiver_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB
            """
        )
        conn.commit()
        print("✅ Verified messages table")
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"⚠️ Failed to ensure messages schema: {err}")
    finally:
        cursor.close()
        conn.close()


def ensure_gifts_schema():
    """Ensure gift-related columns and tables exist for content gifting."""
    conn = get_db_connection()
    if not conn:
        print("⚠️ Could not verify gifts schema (no DB connection)")
        return

    cursor = conn.cursor(dictionary=True)

    def ensure_column(table_name, column_name, definition_sql):
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            """,
            (DB_CONFIG['database'], table_name, column_name)
        )
        exists = cursor.fetchone()['count'] > 0
        if not exists:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition_sql}")
            print(f"✅ Added {table_name}.{column_name} column")

    try:
        ensure_column('photos', 'allow_gifts', 'TINYINT(1) NOT NULL DEFAULT 1')
        ensure_column('videos', 'allow_gifts', 'TINYINT(1) NOT NULL DEFAULT 1')
        ensure_column('posts', 'allow_gifts', 'TINYINT(1) NOT NULL DEFAULT 1')
        ensure_column('reels', 'allow_gifts', 'TINYINT(1) NOT NULL DEFAULT 1')

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gifts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                content_type ENUM('photo', 'video', 'post', 'reel') NOT NULL,
                content_id INT NOT NULL,
                gift_name VARCHAR(100) NOT NULL,
                gift_icon VARCHAR(20),
                gift_price DECIMAL(10,2) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_receiver (receiver_id),
                INDEX idx_content (content_type, content_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB
            """
        )
        print("✅ Verified gifts table")
        conn.commit()
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"⚠️ Failed to ensure gifts schema: {err}")
    finally:
        cursor.close()
        conn.close()

# Database Connection Helper
def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None


def get_punctuation_model():
    """Lazily initialize punctuation model so server startup stays fast."""
    global PUNCT_MODEL

    if PUNCT_MODEL is not None:
        return PUNCT_MODEL

    if PunctuationModel is None:
        return None

    PUNCT_MODEL = PunctuationModel()
    return PUNCT_MODEL


ensure_users_schema_columns()
ensure_messages_schema()
ensure_gifts_schema()

# JWT Token Decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(current_user_id, *args, **kwargs)
    
    return decorated

# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    username = data.get('username', email.split('@')[0])
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (email, password, username, created_at) VALUES (%s, %s, %s, %s)",
            (email, hashed_password, username, datetime.datetime.now())
        )
        conn.commit()
        user_id = cursor.lastrowid
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user_id,
            'email': email,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'message': 'User created successfully',
            'token': token,
            'user': {
                'id': user_id,
                'email': email,
                'username': username,
                'bio': 'Add a short bio about yourself — what you do and what people can expect from your content.',
                'profile_picture': None,
                'email_public': 0
            }
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Generate JWT token
        token = jwt.encode({
            'user_id': user['id'],
            'email': user['email'],
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'username': user['username'],
                'bio': user['bio'],
                'profile_picture': user['profile_picture'],
                'email_public': user.get('email_public', 0)
            }
        }), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# PROFILE ENDPOINTS
# ============================================

@app.route('/api/profile', methods=['GET'])
@token_required
def get_profile(current_user_id):
    """Get current user profile."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (current_user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Remove password from response
        del user['password']
        
        return jsonify(user), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/profile', methods=['PUT'])
@token_required
def update_profile(current_user_id):
    """Update current user profile."""
    data = request.json
    user_id = current_user_id
    
    print(f"📝 Updating profile for user {user_id}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        # Build dynamic update query
        update_fields = []
        values = []
        
        allowed_fields = ['username', 'bio', 'profile_picture', 'phone', 'location', 'email_public']
        for field in allowed_fields:
            if field in data:
                if field == 'email_public':
                    values.append(1 if data[field] else 0)
                    update_fields.append(f"{field} = %s")
                    continue
                update_fields.append(f"{field} = %s")
                values.append(data[field])
        
        if not update_fields:
            return jsonify({'error': 'No fields to update'}), 400
        
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, tuple(values))
        conn.commit()
        
        print(f"✅ Profile updated for user {user_id}")
        
        return jsonify({'message': 'Profile updated successfully'}), 200
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"❌ Profile update error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# USER DISCOVERY ENDPOINTS
# ============================================

@app.route('/api/users/discover', methods=['GET'])
def discover_users():
    """Discover users by username or email (public endpoint for user search)."""
    query = (request.args.get('q') or '').strip()
    limit = request.args.get('limit', default=50, type=int)
    limit = min(max(limit, 1), 100)

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        sql = """
                 SELECT id,
                     CASE WHEN email_public = 1 THEN email ELSE NULL END AS email,
                     username,
                     profile_picture,
                     email_public,
                     created_at
            FROM users
        """
        params = []

        if query:
            sql += " WHERE LOWER(username) LIKE %s OR (email_public = 1 AND LOWER(email) LIKE %s)"
            like_query = f"%{query.lower()}%"
            params.extend([like_query, like_query])

        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(sql, tuple(params))
        users = cursor.fetchall()

        response = []
        for user in users:
            user_data = {
                'id': user['id'],
                'name': user.get('username') or 'User',
                'email': user.get('email') or '',
                'profilePicture': user.get('profile_picture') or '',
                'email_public': user.get('email_public', 0)
            }
            # Debug log
            if user_data['profilePicture']:
                print(f"✓ User {user_data['name']} has profile_picture: {user_data['profilePicture'][:50]}...")
            response.append(user_data)

        print(f"Returning {len(response)} users from /api/users/discover")
        return jsonify(response), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Get a specific user's public profile by ID (public endpoint)."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
                 SELECT id,
                     CASE WHEN email_public = 1 THEN email ELSE NULL END AS email,
                     username,
                     profile_picture,
                     bio,
                     email_public,
                     created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Debug log
        if user.get('profile_picture'):
            print(f"✓ User {user['username']} profile_picture in DB: {user['profile_picture'][:50]}...")

        # Get user's content counts
        cursor.execute("SELECT COUNT(*) as count FROM photos WHERE user_id = %s", (user_id,))
        photos_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM videos WHERE user_id = %s", (user_id,))
        videos_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM posts WHERE user_id = %s", (user_id,))
        posts_count = cursor.fetchone()['count']

        response = {
            'id': user['id'],
            'username': user.get('username') or 'User',
            'name': user.get('username') or 'User',
            'email': user.get('email') or '',
            'email_public': user.get('email_public', 0),
            'profilePicture': user.get('profile_picture') or '',
            'bio': user.get('bio') or '',
            'createdAt': user.get('created_at').isoformat() if user.get('created_at') else None,
            'stats': {
                'photos': photos_count,
                'videos': videos_count,
                'posts': posts_count,
                'total': photos_count + videos_count + posts_count
            }
        }

        return jsonify(response), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# Debug endpoint to check users with profile pictures
@app.route('/api/debug/users-with-pictures', methods=['GET'])
def debug_users_with_pictures():
    """Debug endpoint to see which users have profile pictures."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, username, email, 
                   CASE 
                       WHEN profile_picture IS NULL THEN 'NULL'
                       WHEN profile_picture = '' THEN 'EMPTY'
                       ELSE CONCAT(LEFT(profile_picture, 30), '...')
                   END as picture_status
            FROM users
            ORDER BY id
            LIMIT 20
        """)
        users = cursor.fetchall()

        return jsonify({
            'total_users': len(users),
            'users': users
        }), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# USER CONTENT ENDPOINTS
# ============================================

@app.route('/api/users/<int:user_id>/photos', methods=['GET'])
def get_user_photos(user_id):
    """Get all photos for a specific user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, title, description, photo_data, created_at, likes_count,
                   COALESCE(allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'photo' AND g.content_id = photos.id
                   ) as gifts_count
            FROM photos
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        
        photos = cursor.fetchall()
        
        return jsonify(photos), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/users/<int:user_id>/videos', methods=['GET'])
def get_user_videos(user_id):
    """Get all videos for a specific user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, title, description, video_data, thumbnail_data, created_at, likes_count,
                   COALESCE(allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'video' AND g.content_id = videos.id
                   ) as gifts_count
            FROM videos
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        
        videos = cursor.fetchall()
        
        return jsonify(videos), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/users/<int:user_id>/posts', methods=['GET'])
def get_user_posts(user_id):
    """Get all posts for a specific user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, content, created_at, likes_count,
                   COALESCE(allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'post' AND g.content_id = posts.id
                   ) as gifts_count
            FROM posts
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        
        posts = cursor.fetchall()
        
        return jsonify(posts), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# PHOTO ENDPOINTS
# ============================================

@app.route('/api/photos', methods=['POST'])
@token_required
def upload_photo(current_user_id):
    """Upload a photo for current user."""
    data = request.json
    title = data.get('title')
    description = data.get('description', '')
    photo_data = data.get('photo')  # Base64 encoded image
    profile_picture = data.get('profile_picture')  # Optional: profile picture from frontend
    allow_gifts = bool(data.get('allow_gifts', True))
    
    from detection import is_blocked
    if not title or not photo_data:
        return jsonify({'error': 'Title and photo required'}), 400
    if is_blocked(title) or is_blocked(description):
        return jsonify({'error': 'Upload blocked: inappropriate words detected in title or description.'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        # Decode base64 image
        if ',' in photo_data:  # Remove data:image/...;base64, prefix
            photo_data = photo_data.split(',')[1]
        
        photo_blob = base64.b64decode(photo_data)
        
        cursor.execute(
                """INSERT INTO photos (user_id, title, description, photo_data, allow_gifts, created_at) 
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                (current_user_id, title, description, photo_blob, allow_gifts, datetime.datetime.now())
        )
        conn.commit()
        photo_id = cursor.lastrowid
        
        return jsonify({
            'message': 'Photo uploaded successfully',
            'photo_id': photo_id
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/photos', methods=['GET'])
def get_photos():
    """Get all photos with user information (authentication disabled for development)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """SELECT 
                p.id, 
                p.user_id,
                p.title, 
                p.description, 
                p.created_at,
                COALESCE(p.allow_gifts, 1) as allow_gifts,
                (
                    SELECT COUNT(*)
                    FROM gifts g
                    WHERE g.content_type = 'photo' AND g.content_id = p.id
                ) as gifts_count,
                u.username,
                u.profile_picture
            FROM photos p
            LEFT JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC"""
        )
        photos = cursor.fetchall()
        
        # Convert datetime to string
        for photo in photos:
            photo['created_at'] = photo['created_at'].isoformat()
        
        return jsonify(photos), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/photos/<int:photo_id>', methods=['GET'])
def get_photo_image(photo_id):
    """Get photo image data"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT photo_data FROM photos WHERE id = %s", (photo_id,))
        photo = cursor.fetchone()
        
        if not photo:
            return jsonify({'error': 'Photo not found'}), 404
        
        # Return image as base64
        photo_base64 = base64.b64encode(photo['photo_data']).decode('utf-8')
        return jsonify({'photo': f'data:image/jpeg;base64,{photo_base64}'}), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
@token_required
def delete_photo(current_user_id, photo_id):
    """Delete a photo belonging to current user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "DELETE FROM photos WHERE id = %s AND user_id = %s",
            (photo_id, current_user_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Photo not found or unauthorized'}), 404
        
        return jsonify({'message': 'Photo deleted successfully'}), 200
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# VIDEO ENDPOINTS
# ============================================

@app.route('/api/videos', methods=['POST'])
@token_required
def upload_video(current_user_id):
    """Upload a video for current user."""
    data = request.json
    title = data.get('title')
    description = data.get('description', '')
    video_data = data.get('video')  # Base64 encoded video
    profile_picture = data.get('profile_picture')  # Optional: profile picture from frontend
    allow_gifts = bool(data.get('allow_gifts', True))
    
    from detection import is_blocked
    if not title or not video_data:
        return jsonify({'error': 'Title and video required'}), 400
    if is_blocked(title) or is_blocked(description):
        return jsonify({'error': 'Upload blocked: inappropriate words detected in title or description.'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        # Decode base64 video
        if ',' in video_data:
            video_data = video_data.split(',')[1]
        
        video_blob = base64.b64decode(video_data)
        
        cursor.execute(
                """INSERT INTO videos (user_id, title, description, video_data, allow_gifts, created_at) 
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                (current_user_id, title, description, video_blob, allow_gifts, datetime.datetime.now())
        )
        conn.commit()
        video_id = cursor.lastrowid
        
        return jsonify({
            'message': 'Video uploaded successfully',
            'video_id': video_id
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/videos', methods=['GET'])
def get_videos():
    """Get all videos with user information (authentication disabled for development)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """SELECT 
                v.id, 
                v.user_id,
                v.title, 
                v.description, 
                v.created_at,
                COALESCE(v.allow_gifts, 1) as allow_gifts,
                (
                    SELECT COUNT(*)
                    FROM gifts g
                    WHERE g.content_type = 'video' AND g.content_id = v.id
                ) as gifts_count,
                u.username,
                u.profile_picture
            FROM videos v
            LEFT JOIN users u ON v.user_id = u.id
            ORDER BY v.created_at DESC"""
        )
        videos = cursor.fetchall()
        
        for video in videos:
            video['created_at'] = video['created_at'].isoformat()
        
        return jsonify(videos), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/videos/<int:video_id>', methods=['DELETE'])
@token_required
def delete_video(current_user_id, video_id):
    """Delete a video belonging to current user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "DELETE FROM videos WHERE id = %s AND user_id = %s",
            (video_id, current_user_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Video not found or unauthorized'}), 404
        
        return jsonify({'message': 'Video deleted successfully'}), 200
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# POST ENDPOINTS
# ============================================

@app.route('/api/posts', methods=['POST'])
@token_required
def create_post(current_user_id):
    """Create a text post for current user."""
    data = request.json
    title = data.get('title')
    content = data.get('content')
    profile_picture = data.get('profile_picture')  # Optional: profile picture from frontend
    allow_gifts = bool(data.get('allow_gifts', True))
    user_id = current_user_id
    
    print(f"📝 Creating post - user_id: {user_id}, title: {title}")
    
    from detection import is_blocked
    if not title or not content:
        return jsonify({'error': 'Title and content required'}), 400
    if is_blocked(title) or is_blocked(content):
        return jsonify({'error': 'Post blocked: inappropriate words detected in title or content.'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute(
                """INSERT INTO posts (user_id, title, content, allow_gifts, created_at) 
                    VALUES (%s, %s, %s, %s, %s)""",
                (user_id, title, content, allow_gifts, datetime.datetime.now())
        )
        conn.commit()
        post_id = cursor.lastrowid
        
        print(f"✅ Post created with ID {post_id} for user {user_id}")
        
        return jsonify({
            'message': 'Post created successfully',
            'post_id': post_id,
            'user_id': user_id
        }), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"❌ Post creation error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Get all posts with user information (authentication disabled for development)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """SELECT 
                p.id, 
                p.user_id, 
                p.title, 
                p.content, 
                p.created_at,
                COALESCE(p.likes_count, 0) as likes_count,
                COALESCE(p.allow_gifts, 1) as allow_gifts,
                (
                    SELECT COUNT(*)
                    FROM gifts g
                    WHERE g.content_type = 'post' AND g.content_id = p.id
                ) as gifts_count,
                (
                    SELECT COUNT(*)
                    FROM comments c
                    WHERE c.content_type = 'post' AND c.content_id = p.id
                ) as comments_count,
                u.username,
                u.profile_picture
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC"""
        )
        posts = cursor.fetchall()
        
        for post in posts:
            post['created_at'] = post['created_at'].isoformat()
            print(f"📝 Post {post['id']}: user_id={post['user_id']}, username={post['username']}, has_picture={bool(post['profile_picture'])}")
        
        print(f"✅ Returning {len(posts)} posts with user info")
        return jsonify(posts), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(current_user_id, post_id):
    """Delete a post belonging to current user."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "DELETE FROM posts WHERE id = %s AND user_id = %s",
            (post_id, current_user_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Post not found or unauthorized'}), 404
        
        return jsonify({'message': 'Post deleted successfully'}), 200
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# FEED ENDPOINT
# ============================================

@app.route('/api/feed', methods=['GET'])
def get_feed():
    """Get combined feed of all content (authentication disabled for development)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get all photos, videos, and posts from all users
        feed_items = []
        
        # Photos
        cursor.execute("""
            SELECT p.id, p.title, p.description, p.created_at,
                   COALESCE(p.allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'photo' AND g.content_id = p.id
                   ) as gifts_count,
                   u.username, u.profile_picture, 'photo' as type
            FROM photos p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 50
        """)
        photos = cursor.fetchall()
        for photo in photos:
            photo['created_at'] = photo['created_at'].isoformat()
            feed_items.append(photo)
        
        # Videos
        cursor.execute("""
            SELECT v.id, v.title, v.description, v.created_at,
                   COALESCE(v.allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'video' AND g.content_id = v.id
                   ) as gifts_count,
                   u.username, u.profile_picture, 'video' as type
            FROM videos v
            JOIN users u ON v.user_id = u.id
            ORDER BY v.created_at DESC
            LIMIT 50
        """)
        videos = cursor.fetchall()
        for video in videos:
            video['created_at'] = video['created_at'].isoformat()
            feed_items.append(video)
        
        # Posts
        cursor.execute("""
            SELECT p.id, p.title, p.content, p.created_at,
                   COALESCE(p.allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'post' AND g.content_id = p.id
                   ) as gifts_count,
                   u.username, u.profile_picture, 'post' as type
            FROM posts p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 50
        """)
        posts = cursor.fetchall()
        for post in posts:
            post['created_at'] = post['created_at'].isoformat()
            feed_items.append(post)
        
        # Sort all by date
        feed_items.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify(feed_items[:50]), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# LIKES ENDPOINTS
# ============================================

@app.route('/api/likes', methods=['POST'])
@token_required
def add_like(current_user_id):
    """Add a like to a post, photo, video, or reel"""
    data = request.json
    content_type = data.get('content_type')  # 'post', 'photo', 'video', 'reel'
    content_id = data.get('content_id')
    
    if not content_type or not content_id:
        return jsonify({'error': 'content_type and content_id required'}), 400
    
    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        # Try to insert like (UNIQUE constraint prevents duplicates)
        cursor.execute(
            """INSERT INTO likes (user_id, content_type, content_id, created_at) 
               VALUES (%s, %s, %s, %s)""",
            (current_user_id, content_type, content_id, datetime.datetime.now())
        )
        conn.commit()
        
        return jsonify({'message': 'Like added successfully'}), 201
        
    except mysql.connector.Error as err:
        conn.rollback()
        if 'Duplicate entry' in str(err):
            return jsonify({'error': 'You already liked this content'}), 409
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/likes/<string:content_type>/<int:content_id>', methods=['DELETE'])
@token_required
def remove_like(current_user_id, content_type, content_id):
    """Remove a like from content"""
    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """DELETE FROM likes 
               WHERE user_id = %s AND content_type = %s AND content_id = %s""",
            (current_user_id, content_type, content_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Like not found'}), 404
        
        return jsonify({'message': 'Like removed successfully'}), 200
        
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/likes/<string:content_type>/<int:content_id>/check', methods=['GET'])
@token_required
def check_like(current_user_id, content_type, content_id):
    """Check if current user has liked this content"""
    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """SELECT id FROM likes 
               WHERE user_id = %s AND content_type = %s AND content_id = %s""",
            (current_user_id, content_type, content_id)
        )
        like = cursor.fetchone()
        
        return jsonify({'liked': like is not None}), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/likes-count/<string:content_type>/<int:content_id>', methods=['GET'])
def get_likes_count(content_type, content_id):
    """Get total like count for content"""
    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """SELECT COUNT(*) as count FROM likes 
               WHERE content_type = %s AND content_id = %s""",
            (content_type, content_id)
        )
        result = cursor.fetchone()
        
        return jsonify({'likes': result['count']}), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# GIFTS ENDPOINTS
# ============================================

@app.route('/api/gifts', methods=['POST'])
@token_required
def send_gift(current_user_id):
    """Send a gift to a content owner when gifts are enabled on that content."""
    data = request.json or {}
    content_type = (data.get('content_type') or '').strip().lower()
    content_id = data.get('content_id')
    gift_name = (data.get('gift_name') or 'Gift').strip()[:100]
    gift_icon = (data.get('gift_icon') or '🎁').strip()[:20]
    gift_price = data.get('gift_price', 0)

    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400

    if not content_id:
        return jsonify({'error': 'content_id is required'}), 400

    try:
        content_id = int(content_id)
        gift_price = float(gift_price or 0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid content_id or gift_price'}), 400

    table_map = {
        'photo': 'photos',
        'video': 'videos',
        'post': 'posts',
        'reel': 'reels'
    }
    table_name = table_map[content_type]

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            f"SELECT user_id, COALESCE(allow_gifts, 1) AS allow_gifts FROM {table_name} WHERE id = %s",
            (content_id,)
        )
        content_row = cursor.fetchone()

        if not content_row:
            return jsonify({'error': 'Content not found'}), 404

        if not bool(content_row.get('allow_gifts', 1)):
            return jsonify({'error': 'Gifts are disabled for this content'}), 403

        receiver_id = content_row['user_id']
        if int(receiver_id) == int(current_user_id):
            return jsonify({'error': 'You cannot send a gift to your own content'}), 400

        cursor.execute(
            """
            INSERT INTO gifts (sender_id, receiver_id, content_type, content_id, gift_name, gift_icon, gift_price, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (current_user_id, receiver_id, content_type, content_id, gift_name, gift_icon, gift_price, datetime.datetime.now())
        )

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM gifts
            WHERE content_type = %s AND content_id = %s
            """,
            (content_type, content_id)
        )
        gifts_count = cursor.fetchone()['count']

        conn.commit()
        return jsonify({
            'message': 'Gift sent successfully',
            'gifts_count': gifts_count
        }), 201

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/gifts-count/<string:content_type>/<int:content_id>', methods=['GET'])
def get_gifts_count(content_type, content_id):
    """Get total gifts count for a content item."""
    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM gifts
            WHERE content_type = %s AND content_id = %s
            """,
            (content_type, content_id)
        )
        row = cursor.fetchone()
        return jsonify({'gifts': row['count'] if row else 0}), 200
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# COMMENTS ENDPOINTS
# ============================================

@app.route('/api/comments', methods=['POST'])
@token_required
def add_comment(current_user_id):
    """Add a comment to a post, photo, video, or reel."""
    data = request.json
    content_type = data.get('content_type')
    content_id = data.get('content_id')
    comment = (data.get('comment') or '').strip()

    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400

    if not content_id or not comment:
        return jsonify({'error': 'content_id and comment are required'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor()

    try:
        cursor.execute(
            """INSERT INTO comments (user_id, content_type, content_id, comment, created_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (current_user_id, content_type, content_id, comment, datetime.datetime.now())
        )
        conn.commit()

        return jsonify({'message': 'Comment added successfully', 'comment_id': cursor.lastrowid}), 201

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/comments/<string:content_type>/<int:content_id>', methods=['GET'])
def get_comments(content_type, content_id):
    """Get comments for a specific content item."""
    if content_type not in ['photo', 'video', 'post', 'reel']:
        return jsonify({'error': 'Invalid content_type'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """SELECT
                c.id,
                c.user_id,
                c.comment,
                c.created_at,
                u.username,
                u.profile_picture
            FROM comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.content_type = %s AND c.content_id = %s
            ORDER BY c.created_at ASC""",
            (content_type, content_id)
        )
        comments = cursor.fetchall()

        for row in comments:
            row['created_at'] = row['created_at'].isoformat() if row.get('created_at') else None

        return jsonify(comments), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(current_user_id, comment_id):
    """Delete current user's comment."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM comments WHERE id = %s AND user_id = %s",
            (comment_id, current_user_id)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'error': 'Comment not found or unauthorized'}), 404

        return jsonify({'message': 'Comment deleted successfully'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# AI TEXT TOOLS ENDPOINTS
# ============================================

@app.route('/api/ai/punctuate', methods=['POST'])
def punctuate_text():
    """Restore punctuation using deepmultilingualpunctuation model."""
    data = request.json or {}
    text = (data.get('text') or '').strip()

    if not text:
        return jsonify({'error': 'text is required'}), 400

    model = get_punctuation_model()
    if model is None:
        return jsonify({
            'error': 'Punctuation model is unavailable on server. Install deepmultilingualpunctuation.',
            'detail': PUNCT_IMPORT_ERROR
        }), 500

    try:
        punctuated = model.restore_punctuation(text)
        return jsonify({
            'success': True,
            'text': punctuated,
            'punctuatedText': punctuated
        }), 200
    except Exception as err:
        return jsonify({'error': str(err)}), 500


# ============================================
# MESSAGES ENDPOINTS
# ============================================

@app.route('/api/messages/conversations', methods=['GET'])
@token_required
def get_message_conversations(current_user_id):
    """List conversations for the current user, grouped by chat partner."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                m.id,
                m.sender_id,
                m.receiver_id,
                m.message,
                m.created_at,
                CASE WHEN m.sender_id = %s THEN m.receiver_id ELSE m.sender_id END AS partner_id,
                u.username AS partner_username,
                u.profile_picture AS partner_profile_picture
            FROM messages m
            JOIN users u
              ON u.id = CASE WHEN m.sender_id = %s THEN m.receiver_id ELSE m.sender_id END
            WHERE m.sender_id = %s OR m.receiver_id = %s
            ORDER BY m.created_at DESC
            """,
            (current_user_id, current_user_id, current_user_id, current_user_id)
        )
        rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT sender_id, COUNT(*) AS unread_count
            FROM messages
            WHERE receiver_id = %s AND is_read = 0
            GROUP BY sender_id
            """,
            (current_user_id,)
        )
        unread_rows = cursor.fetchall()
        unread_map = {int(row['sender_id']): int(row['unread_count']) for row in unread_rows}

        seen_partners = set()
        conversations = []

        for row in rows:
            partner_id = int(row['partner_id'])
            if partner_id in seen_partners:
                continue
            seen_partners.add(partner_id)

            created_at = row.get('created_at')
            conversations.append({
                'partner_id': partner_id,
                'partner_name': row.get('partner_username') or 'User',
                'partner_profile_picture': row.get('partner_profile_picture'),
                'last_message': row.get('message') or '',
                'last_message_at': created_at.isoformat() if created_at else None,
                'unread_count': unread_map.get(partner_id, 0)
            })

        return jsonify(conversations), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/messages/<int:partner_id>', methods=['GET'])
@token_required
def get_message_thread(current_user_id, partner_id):
    """Get all messages between current user and partner user."""
    if current_user_id == partner_id:
        return jsonify({'error': 'Cannot open a chat with yourself'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT id, username, profile_picture FROM users WHERE id = %s",
            (partner_id,)
        )
        partner = cursor.fetchone()
        if not partner:
            return jsonify({'error': 'User not found'}), 404

        cursor.execute(
            """
            SELECT
                id,
                sender_id,
                receiver_id,
                message,
                created_at,
                is_read
            FROM messages
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY created_at ASC
            """,
            (current_user_id, partner_id, partner_id, current_user_id)
        )
        rows = cursor.fetchall()

        cursor.execute(
            """
            UPDATE messages
            SET is_read = 1
            WHERE sender_id = %s AND receiver_id = %s AND is_read = 0
            """,
            (partner_id, current_user_id)
        )
        conn.commit()

        messages = []
        for row in rows:
            created_at = row.get('created_at')
            messages.append({
                'id': row['id'],
                'sender_id': row['sender_id'],
                'receiver_id': row['receiver_id'],
                'message': row['message'],
                'created_at': created_at.isoformat() if created_at else None,
                'is_read': bool(row.get('is_read', 0)),
                'sent_by_me': int(row['sender_id']) == int(current_user_id)
            })

        return jsonify({
            'partner': {
                'id': partner['id'],
                'name': partner.get('username') or 'User',
                'profile_picture': partner.get('profile_picture')
            },
            'messages': messages
        }), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/messages', methods=['POST'])
@token_required
def send_message(current_user_id):
    """Send a direct message from current user to another user."""
    data = request.json or {}
    receiver_id = data.get('receiver_id')
    message_text = (data.get('message') or '').strip()

    if not receiver_id or not message_text:
        return jsonify({'error': 'receiver_id and message are required'}), 400

    try:
        receiver_id = int(receiver_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'receiver_id must be an integer'}), 400

    if receiver_id == current_user_id:
        return jsonify({'error': 'Cannot send message to yourself'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM users WHERE id = %s", (receiver_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Receiver not found'}), 404

        created_at = datetime.datetime.now()
        cursor.execute(
            """
            INSERT INTO messages (sender_id, receiver_id, message, created_at, is_read)
            VALUES (%s, %s, %s, %s, 0)
            """,
            (current_user_id, receiver_id, message_text, created_at)
        )
        conn.commit()

        return jsonify({
            'message': 'Message sent successfully',
            'data': {
                'id': cursor.lastrowid,
                'sender_id': current_user_id,
                'receiver_id': receiver_id,
                'message': message_text,
                'created_at': created_at.isoformat(),
                'is_read': False,
                'sent_by_me': True
            }
        }), 201

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/messages/<int:message_id>', methods=['DELETE'])
@token_required
def delete_message(current_user_id, message_id):
    """Delete one of the current user's sent messages."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM messages WHERE id = %s AND sender_id = %s",
            (message_id, current_user_id)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'error': 'Message not found or unauthorized'}), 404

        return jsonify({'message': 'Message deleted successfully'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# NOTIFICATIONS
# ============================================

@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(current_user_id):
    """Get all notifications for the current user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT n.*, u.username as from_username, u.profile_picture as from_user_picture
            FROM notifications n
            LEFT JOIN users u ON n.from_user_id = u.id
            WHERE n.user_id = %s
            ORDER BY n.created_at DESC
            LIMIT 100
        ''', (current_user_id,))
        
        notifications = cursor.fetchall()
        
        # Convert datetime to ISO format
        for notif in notifications:
            if notif.get('created_at'):
                notif['created_at'] = notif['created_at'].isoformat()
        
        return jsonify(notifications), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/notifications/unread-count', methods=['GET'])
@token_required
def get_unread_notifications_count(current_user_id):
    """Get count of unread notifications"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM notifications
            WHERE user_id = %s AND is_read = FALSE
        ''', (current_user_id,))
        
        result = cursor.fetchone()
        return jsonify({'count': result['count'] if result else 0}), 200

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/notifications', methods=['POST'])
@token_required
def create_notification(current_user_id):
    """Create a new notification"""
    data = request.get_json()
    
    if not data or not data.get('to_user_id') or not data.get('type'):
        return jsonify({'error': 'Missing required fields: to_user_id, type'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Don't create notification if notifying yourself
        if int(data['to_user_id']) == current_user_id:
            return jsonify({'message': 'Cannot notify yourself'}), 200
        
        # Prepare notification data
        notification_type = data['type']
        to_user_id = int(data['to_user_id'])
        content_type = data.get('content_type', '')
        content_id = data.get('content_id', 0)
        action_data = data.get('action_data', '{}')
        
        # Create message based on type
        if notification_type == 'like':
            message = f"liked your {content_type}"
        elif notification_type == 'comment':
            message = f"commented on your {content_type}"
        elif notification_type == 'share':
            message = f"shared your {content_type}"
        elif notification_type == 'message':
            message = "sent you a message"
        else:
            message = data.get('message', 'interacted with your content')
        
        cursor.execute('''
            INSERT INTO notifications 
            (user_id, from_user_id, type, message, content_type, content_id, action_data, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, NOW())
        ''', (to_user_id, current_user_id, notification_type, message, content_type, content_id, action_data))
        
        conn.commit()
        notification_id = cursor.lastrowid
        
        return jsonify({
            'message': 'Notification created successfully',
            'notification_id': notification_id
        }), 201

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@token_required
def mark_notification_read(current_user_id, notification_id):
    """Mark a notification as read"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notifications
            SET is_read = TRUE
            WHERE id = %s AND user_id = %s
        ''', (notification_id, current_user_id))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Notification not found'}), 404
        
        return jsonify({'message': 'Notification marked as read'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/notifications/mark-all-read', methods=['PUT'])
@token_required
def mark_all_notifications_read(current_user_id):
    """Mark all notifications as read for current user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = %s AND is_read = FALSE
        ''', (current_user_id,))
        
        conn.commit()
        updated_count = cursor.rowcount
        
        return jsonify({
            'message': 'All notifications marked as read',
            'count': updated_count
        }), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@token_required
def delete_notification(current_user_id, notification_id):
    """Delete a specific notification"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM notifications
            WHERE id = %s AND user_id = %s
        ''', (notification_id, current_user_id))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Notification not found'}), 404
        
        return jsonify({'message': 'Notification deleted successfully'}), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/notifications/clear-all', methods=['DELETE'])
@token_required
def clear_all_notifications(current_user_id):
    """Delete all notifications for current user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM notifications
            WHERE user_id = %s
        ''', (current_user_id,))
        
        conn.commit()
        deleted_count = cursor.rowcount
        
        return jsonify({
            'message': 'All notifications cleared',
            'count': deleted_count
        }), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# SEARCH ENDPOINTS
# ============================================

@app.route('/api/products/search', methods=['GET'])
def search_products():
    """Search products by title or description"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not query or len(query) < 2:
        return jsonify([]), 200
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        search_term = f"%{query}%"
        cursor.execute("""
            SELECT p.id, p.title, p.description, p.price, p.category, p.created_at,
                   u.username, u.profile_picture
            FROM products p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.title LIKE %s OR p.description LIKE %s
            ORDER BY p.created_at DESC
            LIMIT %s
        """, (search_term, search_term, limit))
        
        products = cursor.fetchall()
        for product in products:
            product['created_at'] = product['created_at'].isoformat() if product['created_at'] else None
        
        return jsonify(products), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/users/search', methods=['GET'])
def search_users():
    """Search users by username or bio"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not query or len(query) < 2:
        return jsonify([]), 200
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        search_term = f"%{query}%"
        cursor.execute("""
            SELECT id, username, bio, profile_picture, location, created_at
            FROM users
            WHERE username LIKE %s OR bio LIKE %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (search_term, search_term, limit))
        
        users = cursor.fetchall()
        for user in users:
            user['created_at'] = user['created_at'].isoformat() if user['created_at'] else None
        
        return jsonify(users), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/api/posts/search', methods=['GET'])
def search_posts():
    """Search posts by title or content"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not query or len(query) < 2:
        return jsonify([]), 200
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        search_term = f"%{query}%"
        cursor.execute("""
            SELECT p.id, p.title, p.content, p.created_at,
                   COALESCE(p.likes_count, 0) as likes_count,
                   COALESCE(p.allow_gifts, 1) as allow_gifts,
                   (
                       SELECT COUNT(*)
                       FROM gifts g
                       WHERE g.content_type = 'post' AND g.content_id = p.id
                   ) as gifts_count,
                   (
                       SELECT COUNT(*)
                       FROM comments c
                       WHERE c.content_type = 'post' AND c.content_id = p.id
                   ) as comments_count,
                   u.username, u.profile_picture
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.title LIKE %s OR p.content LIKE %s
            ORDER BY p.created_at DESC
            LIMIT %s
        """, (search_term, search_term, limit))
        
        posts = cursor.fetchall()
        for post in posts:
            post['created_at'] = post['created_at'].isoformat() if post['created_at'] else None
        
        return jsonify(posts), 200
        
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================
# HEALTH CHECK
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    else:
        return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 500

if __name__ == '__main__':
    print("🚀 Coshin.com Backend Server Starting...")
    print("📡 API running on http://localhost:$PORT")
    # Get local IP for mobile/LAN access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        print(f"📱 Phone/LAN access: http://{local_ip}:$PORT")
    except:
        print("📱 Phone/LAN access: http://<your-pc-ip>:$PORT")
    print("💾 Make sure MySQL is running and database 'zimcom' exists")
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host='0.0.0.0', port=port)
