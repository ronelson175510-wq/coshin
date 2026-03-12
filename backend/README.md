# Coshin.com Backend Server

Python Flask backend with MySQL database and JWT authentication.

## Installation Steps

### 1. Install Python
- Download Python 3.10+: https://www.python.org/downloads/
- During installation, check "Add Python to PATH"

### 2. Install MySQL
- Download: https://dev.mysql.com/downloads/mysql/
- OR use XAMPP: https://www.apachefriends.org/
- Remember your MySQL root password!

### 3. Setup Database
Open MySQL Command Line or MySQL Workbench and run:
```sql
SOURCE c:/Users/jm175/OneDrive/Desktop/Coshin.com/backend/database_schema.sql
```

OR manually:
1. Open MySQL Workbench
2. File → Run SQL Script
3. Select `database_schema.sql`
4. Click Run

### 4. Install Python Dependencies
Open PowerShell in the backend folder:
```powershell
cd "c:\Users\jm175\OneDrive\Desktop\Coshin.com\backend"
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Create `.env` in `backend/` from `.env.example` and set values:

```env
JWT_SECRET_KEY=replace-with-a-strong-random-secret
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=YOUR_MYSQL_PASSWORD
DB_NAME=Coshin
DB_SSL_MODE=disabled
CORS_ORIGINS=*
```

Important security note:
- Credentials are no longer stored in code.
- Do not commit `backend/.env` to Git.
- Set real values in your hosting provider environment variables (Render/Heroku/etc.).

For production, set `CORS_ORIGINS` to your frontend domains (comma-separated) instead of `*`.

Remote DB notes:
- Set `DB_HOST` to your provider hostname (not `localhost`)
- Keep `DB_PORT` from your provider (usually `3306`)
- If provider requires TLS, set `DB_SSL_MODE=required`
- For stricter cert validation use `DB_SSL_MODE=verify_ca` or `DB_SSL_MODE=verify_identity`
- Optional cert paths: `DB_SSL_CA`, `DB_SSL_CERT`, `DB_SSL_KEY`

### 6. Run the Server
```powershell
python app.py
```

Server will start on: http://localhost:5000

For phone/LAN access, use your computer IP:
- Example: `http://192.168.x.x:5000`

For internet access, deploy backend publicly and set frontend Settings -> API Base URL to your deployed URL.

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/login` - User login

### Profile
- `GET /api/profile` - Get user profile (requires token)
- `PUT /api/profile` - Update profile (requires token)

### Photos
- `POST /api/photos` - Upload photo (requires token)
- `GET /api/photos` - Get user photos (requires token)
- `GET /api/photos/<id>` - Get photo image
- `DELETE /api/photos/<id>` - Delete photo (requires token)

### Videos
- `POST /api/videos` - Upload video (requires token)
- `GET /api/videos` - Get user videos (requires token)

### Posts
- `POST /api/posts` - Create post (requires token)
- `GET /api/posts` - Get user posts (requires token)

### Feed
- `GET /api/feed` - Get combined feed (requires token)

### Health
- `GET /api/health` - Check server status

## Testing the API

Use this test user:
- Email: `test@Coshin.com`
- Password: `testpass123`

Example login request:
```javascript
fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    email: 'test@Coshin.com',
    password: 'testpass123'
  })
})
.then(r => r.json())
.then(data => console.log('Token:', data.token))
```

## Troubleshooting

### MySQL Connection Error
- Make sure MySQL is running
- Check `DB_*` values in `.env`
- Verify database 'Coshin' exists

### Module Import Errors
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Port Already in Use
Change port in `app.py` last line:
```python
app.run(debug=True, port=5001)  # Change to 5001
```
