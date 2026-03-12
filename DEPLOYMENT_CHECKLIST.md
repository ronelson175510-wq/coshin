# 🚀 DEPLOYMENT CHECKLIST - Copy & Paste Ready

Use this checklist to deploy Coshin.com globally in under 30 minutes.

---

## ✅ STEP 1: Create Free Database (5 min)

### Option A: PlanetScale (Recommended - Free MySQL)

1. Go to: https://planetscale.com/
2. Sign up (free)
3. Click "Create database"
   - Name: `Coshin`
   - Region: Choose closest to you
4. Click "Connect" → "Create password"
5. **SAVE THESE VALUES:**
   ```
   DB_HOST=__________.us-east-1.psdb.cloud
   DB_USER=__________
   DB_PASSWORD=__________ 
   DB_NAME=Coshin
   DB_PORT=3306
   DB_SSL_MODE=required
   ```

6. Import database schema:
   - Click "Console" tab
   - Copy/paste contents of `backend/database_schema.sql`
   - Click "Execute"

---

## ✅ STEP 2: Push to GitHub (3 min)

```powershell
# In your Coshin.com folder:
git init
git add .
git commit -m "Initial deployment"

# Create repo on GitHub.com, then:
git remote add origin https://github.com/YOUR_USERNAME/Coshin.git
git branch -M main
git push -u origin main
```

---

## ✅ STEP 3: Deploy Backend to Render (10 min)

1. Go to: https://render.com/
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your `Coshin` repository
5. **Fill in settings:**
   ```
   Name: Coshin-backend
   Region: Oregon (or closest)
   Branch: main
   Root Directory: backend
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   Instance Type: Free
   ```

6. **Add Environment Variables** (click "Advanced" → "Add Environment Variable"):
   ```
   JWT_SECRET_KEY=f955478446c13378ebcd7488c57429913c52b1fa990c45a1ac71fa8369671773
   
   DB_HOST=<paste from PlanetScale>
   DB_PORT=3306
   DB_USER=<paste from PlanetScale>
   DB_PASSWORD=<paste from PlanetScale>
   DB_NAME=Coshin
   DB_SSL_MODE=required
   
   CORS_ORIGINS=*
   ```

7. Click "Create Web Service"
8. **Wait 3-5 minutes** for deployment
9. **SAVE YOUR BACKEND URL:**
   ```
   https://Coshin-backend.onrender.com
   ```
10. Test it: `https://Coshin-backend.onrender.com/api/health`
    - Should return: `{"status": "healthy", "database": "connected"}`

---

## ✅ STEP 4: Deploy Frontend to Vercel (5 min)

1. Go to: https://vercel.com/
2. Sign up with GitHub
3. Click "Add New..." → "Project"
4. Import your `Coshin` repository
5. **Fill in settings:**
   ```
   Framework Preset: Other
   Root Directory: ./
   Build Command: (leave empty)
   Output Directory: (leave empty)
   Install Command: (leave empty)
   ```

6. Click "Deploy"
7. **Wait 2 minutes**
8. **SAVE YOUR FRONTEND URL:**
   ```
   https://Coshin.vercel.app
   ```
   (or whatever Vercel assigns)

---

## ✅ STEP 5: Connect Frontend to Backend (2 min)

**On ANY device (phone, laptop, anywhere in the world):**

1. Open: `https://Coshin.vercel.app/settings.html`
2. Set **API Base URL** to:
   ```
   https://Coshin-backend.onrender.com
   ```
3. Click "Save Settings"
4. You should see: "✓ Connection successful! API is responding."

---

## ✅ STEP 6: Test It! (1 min)

1. Go to: `https://Coshin.vercel.app/signup.html`
2. Create an account
3. Log in
4. **IT WORKS! 🎉**

---

## 📱 Share Your Site

Your live URLs:
- **Main Site:** https://Coshin.vercel.app
- **Backend API:** https://Coshin-backend.onrender.com

Anyone in the world can now access your social media platform!

---

## 🔄 Update Backend CORS (Production Security)

After deployment, update CORS in Render:

1. Go to Render → your service → Environment
2. Change `CORS_ORIGINS` from `*` to:
   ```
   https://Coshin.vercel.app
   ```
3. Click "Save Changes"

---

## 💡 Troubleshooting

**Backend shows "disconnected":**
- Check database credentials in Render environment variables
- Verify database exists in PlanetScale
- Check Render logs for errors

**Frontend can't connect:**
- Verify API URL in Settings matches your Render URL exactly
- Check CORS_ORIGINS includes your Vercel domain
- Test backend health: `https://YOUR_BACKEND.onrender.com/api/health`

**Database connection fails:**
- PlanetScale requires `DB_SSL_MODE=required`
- Verify credentials are copy/pasted correctly
- Check database is not paused/deleted

---

## 📊 Costs

| Service | Cost |
|---------|------|
| Render (Backend) | $0/month |
| Vercel (Frontend) | $0/month |
| PlanetScale (Database) | $0/month |
| **TOTAL** | **$0/month** |

Free tier limits:
- Render: 750 hrs/month (always on)
- Vercel: 100 GB bandwidth
- PlanetScale: 5 GB storage, 1 billion reads

More than enough for thousands of users!

---

## 🎯 You're Done!

Your social media platform is now:
✅ Globally accessible
✅ Running 24/7
✅ Free to host
✅ Scalable

Share it with the world! 🌍
