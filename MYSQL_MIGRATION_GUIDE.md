# 🚀 Coshin.com MySQL Migration Guide

## Installation Steps

### Step 1: Install MySQL

**Option A: MySQL Server (Recommended)**
1. Download: https://dev.mysql.com/downloads/mysql/
2. Run installer, choose "Developer Default"
3. Set root password (remember this!)
4. Keep port 3306

**Option B: XAMPP (Easier)**
1. Download: https://www.apachefriends.org/
2. Install and start MySQL from control panel
3. Default: user=`root`, password=`` (empty)

### Step 2: Create Database

Open MySQL Command Line or MySQL Workbench:

```bash
# Login to MySQL
mysql -u root -p

# Then run:
SOURCE c:/Users/jm175/OneDrive/Desktop/Coshin.com/backend/database_schema.sql
```

OR in MySQL Workbench:
- File → Run SQL Script
- Select `backend/database_schema.sql`
- Click Run

### Step 3: Install Python

1. Download Python 3.10+: https://www.python.org/downloads/
2. **Important**: Check "Add Python to PATH" during installation
3. Verify installation:
```powershell
python --version
```

### Step 4: Install Backend Dependencies

Open PowerShell:

```powershell
cd "c:\Users\jm175\OneDrive\Desktop\Coshin.com\backend"
pip install -r requirements.txt
```

### Step 5: Configure MySQL Password

Edit `backend/app.py` line 22-27:

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YOUR_MYSQL_PASSWORD',  # ← Change this!
    'database': 'Coshin'
}
```

### Step 6: Start the Backend Server

```powershell
cd "c:\Users\jm175\OneDrive\Desktop\Coshin.com\backend"
python app.py
```

You should see:
```
🚀 Coshin.com Backend Server Starting...
📡 API running on http://localhost:5000
💾 Make sure MySQL is running and database 'Coshin' exists
 * Running on http://127.0.0.1:5000
```

### Step 7: Update Your Website

Keep the backend server running, then open your website:

1. Open `login.html` in browser
2. Test login with:
   - Email: `test@Coshin.com`
   - Password: `testpass123`

## What Changed?

### ✅ Replaced Firebase with MySQL
- Authentication now uses JWT tokens
- All data stored in MySQL database
- Files stored as BLOBs (base64)

### ✅ Files Modified
- `login.html` - Updated to use new API
- Created `coshin-api.js` - New API client
- Created `backend/app.py` - Flask server
- Created `backend/database_schema.sql` - Database structure

### ✅ Next Steps Needed

You still need to update these pages to use the new API:
- `signup.html`
- `index.html` (main feed)
- `account.html`
- `upload-photo.html`
- `upload-video.html`
- `create-post.html`
- `upload-reel.html`

## Testing the System

### 1. Test Backend Health

Open browser: http://localhost:5000/api/health

Should see:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### 2. Test Login

Use the test account:
- Email: `test@Coshin.com`
- Password: `testpass123`

### 3. Test API from Browser Console

```javascript
// Login
coshinAPI.login('test@Coshin.com', 'testpass123')
  .then(data => console.log('Logged in:', data))
  .catch(err => console.error('Error:', err));

// Get profile
coshinAPI.getProfile()
  .then(profile => console.log('Profile:', profile));

// Upload photo (requires base64 image)
coshinAPI.uploadPhoto('Test Photo', 'My description', 'data:image/jpeg;base64,...')
  .then(data => console.log('Uploaded:', data));
```

## Troubleshooting

### ❌ "Database connection failed"
- Make sure MySQL is running
- Check username/password in `backend/app.py`
- Verify database 'Coshin' exists: `SHOW DATABASES;`

### ❌ "Cannot import flask"
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### ❌ "CORS error" in browser
The backend already has CORS enabled. Make sure backend is running on port 5000.

### ❌ Port 5000 already in use
Change port in `backend/app.py` line 632:
```python
app.run(debug=True, port=5001)  # Change to 5001
```

Also update `coshin-api.js` line 5:
```javascript
const API_BASE_URL = 'http://localhost:5001/api';
```

## Running in Production

### For Production Use:

1. **Change Secret Key** in `backend/app.py`:
```python
app.config['SECRET_KEY'] = 'use-a-random-secure-key-here'
```

2. **Use Environment Variables**:
```python
import os
DB_CONFIG = {
    'password': os.getenv('MYSQL_PASSWORD', '')
}
```

3. **Disable Debug Mode**:
```python
app.run(debug=False, port=5000)
```

4. **Use Production Server** (Gunicorn):
```powershell
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Need Help?

Check these files:
- `backend/README.md` - Backend documentation
- `backend/database_schema.sql` - Database structure
- `coshin-api.js` - Frontend API client

Common issues:
1. MySQL not running → Start MySQL service
2. Wrong password → Update in `backend/app.py`
3. Database doesn't exist → Run `database_schema.sql`
4. Python modules missing → Run `pip install -r requirements.txt`
