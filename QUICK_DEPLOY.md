# Deploy Coshin.com Globally (Anyone Can Access)

Follow these steps to make your website accessible worldwide.

---

## Step 1: Deploy Backend (10 minutes)

### Option A: Render.com (Recommended - FREE)

1. **Sign up at https://render.com** (use GitHub or email)

2. **Create a free MySQL database:**
   - Click "New +" → "PostgreSQL" (free tier) 
   - **OR use a MySQL provider:**
     - Railway.app (MySQL)
     - PlanetScale.com (FREE MySQL)
     - Aiven.io (FREE tier)

3. **Get database credentials** from your provider (save these):
   - DB_HOST
   - DB_PORT (usually 3306)
   - DB_USER
   - DB_PASSWORD
   - DB_NAME

4. **Import the database schema:**
   - Connect to your cloud database
   - Run the SQL from `backend/database_schema.sql`

5. **Push code to GitHub:**
   ```powershell
   cd "c:\Users\jm175\OneDrive\Desktop\Coshin.com"
   git init
   git add .
   git commit -m "Initial deployment"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/Coshin.git
   git push -u origin main
   ```

6. **Deploy on Render:**
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - **Settings:**
     - Name: `Coshin-backend`
     - Root Directory: `backend`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `gunicorn app:app`
   - **Environment Variables** (click "Add Environment Variable"):
     ```
     JWT_SECRET_KEY=f955478446c13378ebcd7488c57429913c52b1fa990c45a1ac71fa8369671773
     DB_HOST=your-db-host-from-step3
     DB_PORT=3306
     DB_USER=your-db-user
     DB_PASSWORD=your-db-password
     DB_NAME=your-db-name
     DB_SSL_MODE=required
     CORS_ORIGINS=*
     ```
   - Click "Create Web Service"

7. **Wait 3-5 minutes** for deployment to complete.

8. **Copy your backend URL:**
   - Example: `https://Coshin-backend.onrender.com`
   - Test it: `https://Coshin-backend.onrender.com/api/health`

---

## Step 2: Deploy Frontend (5 minutes)

### Option A: Vercel (Recommended - FREE)

1. **Sign up at https://vercel.com** (use GitHub)

2. **Push frontend to GitHub** (already done in Step 1)

3. **Deploy on Vercel:**
   - Click "Add New Project"
   - Import your GitHub repository
   - **Settings:**
     - Framework Preset: Other
     - Root Directory: `./` (leave default)
   - Click "Deploy"

4. **Wait 2 minutes** for deployment.

5. **Get your frontend URL:**
   - Example: `https://Coshin.vercel.app`

---

## Step 3: Connect Frontend to Backend

**On your phone or any device:**

1. Open: `https://Coshin.vercel.app/settings.html`

2. Set **API Base URL** to your Render backend:
   ```
   https://Coshin-backend.onrender.com
   ```

3. Click **Save Settings**

4. Go to **Login** or **Signup**

5. **Create an account** - it works from anywhere now! 🌍

---

## Alternative: Quick Test with Ngrok (No Deployment)

If you want to test globally RIGHT NOW without deploying:

1. **Download ngrok:** https://ngrok.com/download

2. **Start your local backend:**
   ```powershell
   cd "c:\Users\jm175\OneDrive\Desktop\Coshin.com\backend"
   python app.py
   ```

3. **In another terminal, run:**
   ```powershell
   ngrok http 5000
   ```

4. **Copy the ngrok URL** (e.g., `https://abc123.ngrok.io`)

5. **On any device anywhere, go to Settings and set API URL:**
   ```
   https://abc123.ngrok.io
   ```

6. **Now anyone can access it!** (ngrok URL expires after 2 hours on free plan)

---

## Costs Summary

| Service | Plan | Cost |
|---------|------|------|
| Render (Backend) | Free | $0 |
| Vercel (Frontend) | Free | $0 |
| PlanetScale (Database) | Free | $0 |
| **Total** | | **$0/month** |

---

## After Deployment

✅ Your website is now global  
✅ Anyone can signup/login from anywhere  
✅ No need to run anything on your PC  
✅ Works on all devices (phone, tablet, laptop)

**Share your URL:** `https://Coshin.vercel.app`
